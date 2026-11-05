# CUSTBILL local Spark conversion

`launch [ingest|parse|report|chain]` runs each stage independently or the explicit
ingest → parse → report chain. It uses Spark `binaryFiles` for byte-preserving input,
`local[*]`, a nonblocking `flock`, atomic output replacement, and a TRL completion
handshake. `OTTERWORKS_LEGACY_ROOT` selects the root; `CUSTBILL_DISTRIBUTION` and
`CUSTBILL_DELIVERY_DIR` configure delivery without embedding recipients.

Run `make -C etl/custbill-spark setup test lint` from the repository root.
Setup requires an existing system or uv-managed Python 3.12 (the repository
blueprint provides one). It never downloads a managed Python and fails clearly
if no Python 3.12 is installed. Package installation still requires access to
the configured package index/cache. Run Spark parity with
`make -C etl/custbill-spark parity`.

## Legacy awk dialect anomaly

Parsing is pure Python: no awk executable, runtime probe, or host-specific override
is used. Malformed amounts had dialect-dependent output in the legacy chain.
The replacement uses the fixed compatibility rendering below, rather than
following the local machine's gawk/mawk version. This is a deterministic policy,
not a verified description of the GitHub runner's awk: CI logs record passing
tests but do not record its awk implementation/version or signed-infinity output.

| Amount token (case-insensitive) | Fixed rendering |
|---|---|
| Bare `inf`, `nan`, `infinity`; signed `infinity` | `0.00` |
| Signed `+inf` / `-inf` | `+inf` / `-inf` |
| Signed `+nan` / `-nan` | `+nan` / `-nan` |
| Overflow `1e400` / `-1e400` | `+inf` / `-inf` |
| Leading space, tab, CR, vertical tab, form feed | Ignored before numeric-prefix conversion |

These are invalid fixed-width amount fields: every such row is recorded in the
parse ledger and the source is quarantined; `CUSTBILL_STRICT=1` rejects the stage.
Compatibility mode emits the fixed bytes on every host. Tests compare portable
rows against the default `awk` on PATH, and test dialect-dependent rows against
the fixed rendering and ledger errors instead of a host-dependent oracle.

Signed infinity is verified against the real legacy scripts: the 12-byte parse
fields `+inf`, `-inf`, `+Inf`, `-INF`, `+infinity`, and `-infinity` are all
flagged in the ledger and quarantined (strict mode rejects them). Their parse
rendering follows the fixed dialect rule above, not the local awk dialect.
On the development box, the real legacy parse script rendered `+infinity` and
`-infinity` as `+inf` and `-inf`; the replacement deliberately emits `0.00` for
those two tokens. No captured CI output establishes the runner's rendering.
The real Perl report and `report_bytes` agree byte-for-byte: these tokens render
as `Inf` or `-Inf`, mixed positive and negative infinity totals render as `NaN`,
and positive infinity plus a finite amount remains `Inf`.

| Addendum deficiency | Replacement | Deliberate parity limitation / reason |
|---|---|---|
| hostname paths | env root | none |
| stale lock files | real `flock`, released in `finally` | lock file inode remains for safe coordination |
| size settle | TRL handshake + atomic writes | none |
| overlapping schedules | one locked chain | scheduler wiring remains outside this unit |
| sleep dependency | explicit chain function order | none |
| suppressed errors | exceptions and non-zero launcher | none |
| unvalidated fixed width | ledger/quarantine and optional strict mode | non-strict mode preserves legacy bytes |
| unchecked trailer | reconciliation in ledger | non-strict mode preserves legacy output |
| string surgery | byte slicing and typed numeric/date checks | legacy date formatting and numeric-prefix coercion retained |
| CSV renamed `.xls` | verified byte copy | retained because finance pins these bytes |
| silent sendmail | configured delivery copy and SHA receipt | no real email address or email side effect |
| hardcoded recipients | JSON distribution config | none |
| PID temp files | `mkstemp` + atomic rename | none |
| unbounded retention | opt-in digest-checked retention | disabled by default to avoid deleting newer reruns |
| Perl-era implementation | tested Python module | none |
