# CUSTBILL local Spark conversion

`launch [ingest|parse|report|chain]` runs each stage independently or the explicit
ingest → parse → report chain. It uses Spark `binaryFiles` for byte-preserving input,
`local[*]`, a nonblocking `flock`, atomic output replacement, and a TRL completion
handshake. `OTTERWORKS_LEGACY_ROOT` selects the root; `CUSTBILL_DISTRIBUTION` and
`CUSTBILL_DELIVERY_DIR` configure delivery without embedding recipients.

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
