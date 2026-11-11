# UNT-5 security-alert evidence

This is implementation and offline/oracle evidence, **not live Snowflake parity**.
Live commands require explicit coordination. Writes are restricted to the selected
`PC_AUDIT.SECURITY_ALERT` model or newly created `PC_AUDIT_UNT5_FIXTURE` objects.
No command publishes control status or grants privileges.

## Contract

`pc_audit_security_alert` is shared by production, both isolated fixture models,
and the read-only reject analysis. Both SQ/input and expression output string
precisions are 12; trimming is ASCII space only. Critical OPEN becomes ESCALATED.
DEFAULT (including NULL severity) rejects with rowtype 3. Routed NULL keys reject
with rowtype 0 after the runner's failed update/insert. Reject values are unpadded.

PostgreSQL CHAR(12) readback includes trailing spaces. `evidence.snapshot` uses
`evidence.cell`, which preserves strings verbatim, unlike the generic
`compare.normal` string stripping. The model therefore pads non-NULL output
severity/status to 12 and comparisons use `full_compare`; no whitespace
normalization is used to hide differences. NULL and empty remain distinct.

Critical writer finishes before standard writer. A key in both routes gets the
STANDARD value. Within-route duplicate non-NULL keys have no preserved input order
in PC_SRC: the merge source calculates route-key counts and a global maximum,
then divides by zero if any count exceeds one, before its cross-route QUALIFY.
This fails the atomic MERGE (or initial CTAS), not a post-write dbt test. The
duplicate fixture is an intentional difference: runner performs both ordered
updates, whereas dbt must error and preserve its seeded initial target.
The Snowflake runtime guard still needs live execution proof in step B.

Fixtures cover all routes, mixed case/spaces, NULL key in all three routes,
NULL status/actor/document/timestamp, long severity, critical/standard collision,
seed updates, rejected seed preservation, untouched seed, and new inserts.
Landing empty fields mean NULL. The expected target and reject rows are independently
checked against the real local runner by each oracle capture.

## Local captures

Start only a throwaway PostgreSQL container; pass its loopback port in `TD_PORT`.
From `warehouse`, using the warehouse venv (also contains the runner dependencies):

```sh
TD_PORT=56415 .venv/bin/python -m parity.evidence_unt5 oracle --scenario frozen
TD_PORT=56415 .venv/bin/python -m parity.evidence_unt5 oracle --scenario seeded
TD_PORT=56415 .venv/bin/python -m parity.evidence_unt5 oracle --scenario dup_within_route
```

Each command uses a uniquely named local database, bootstraps and seeds it, runs
only `s_m_SFX_SECURITY_ALERT` twice without resetting target state, and drops the
database in a finally block. It stages the committed PSV at
`<runroot>/landing/audit/SECURITY_ALERT/20261109.psv`, sets `LANDING_DIR` to that
landing root, and leaves the XML/session/runner unchanged. Captures retain exact
commands, environment overrides (no credentials), hashes, initial/input/target
typed snapshots, session logs, stdout/stderr, raw .bad files, session results,
per-writer counts, and expected-target comparisons. Frozen input SHA is pinned.

## Coordinated live sequence (not executed in step A)

```sh
.venv/bin/python -m parity.evidence_unt5 preflight
.venv/bin/python -m parity.evidence_unt5 fixture-load
# For each subject: production, seeded, dup_within_route
.venv/bin/python -m parity.evidence_unt5 run --subject seeded --run 1
.venv/bin/python -m parity.evidence_unt5 run --subject seeded --run 2
.venv/bin/python -m parity.evidence_unt5 compare --subject seeded
.venv/bin/python -m parity.evidence_unt5 postflight
.venv/bin/python -m parity.evidence_unt5 index
```

Preflight requires the production initial target to match the frozen oracle's
initial state (absent/empty), validates full typed PC_SRC input in both directions,
and cross-checks PC_BEFORE if present without writing it. It captures all 20 control
rows, query ID and hash. Changed implementation/HEAD or control blocks a build.
Do not rerun preflight to authorize an unexpected initial state: coordinate instead.

Fixture-load refuses an existing fixture schema, creates commented schema/tables,
seeds sources and targets from the oracle initial-state files, and checks readback.
Fixture models are enabled only by `SFX_UNT5_SECURITY_FIXTURE=1` and configure
`PC_AUDIT_UNT5_FIXTURE` inline; shared dbt project config is unchanged.

Builds capture run_results, dbt.log, adapter responses, tagged query history with
insert/update counts, SQL transcripts, targets and compiled read-only reject SQL.
Comparison checks four typed full multisets, key multiplicities, raw .bad line
multisets and typed rejects, route branches, writer/merge counts, and intervening
target writes. Cross-route runner operations become one final-value dbt merge
operation. Duplicate-fixture builds must specifically fail the division guard and
leave the target unchanged. Postflight requires byte-identical control snapshots.

Output: `warehouse/parity/out/evidence/unt5/` (ignored). `index` writes
`evidence_index.json` with per-artifact SHA256/commit and `bundle.tar.gz`.
Capture HEADs remain in lineage/execution files if artifacts span commits;
index's commit is the packaging HEAD. Preserve original evidence, never overwrite
captures or alter the historical UNT-2/UNT-4 lineage gates to accept a new run.

## Live results (2026-11-10)

Production run 1 was built at `8e04db3c14358ae01d360b6ab38bf1a9f462154c`.
Its build and key tests passed, but the collector failed with `invalid identifier
'ROWS_UPDATED'` (query `01c8539f-030d-1e7e-0035-065b001b3ad2`). Read-only
discovery established the supported history columns; collector/test fix
`ab23117bc` removed unsupported fields and used adapter responses and MERGE
RESULT_SCAN instead. Its first recovery attempt stopped with `Cannot prove
uncontaminated run1`: the history window was not bounded to preflight. Fix
`b3a5ddc3181f451f4e153baa2f5550b5488f4495` bounded that window. Both failed
captures remain in the evidence. Run 1 was collected post hoc at this latter
commit, without rebuilding or resetting the target. Executed implementation
hashes equal collected hashes, excluding only the collector; models, macro,
analysis and fixtures are byte-identical to `8e04db3c`.

All subsequent live steps executed at `b3a5ddc3181f451f4e153baa2f5550b5488f4495`.
Preflight, recovery, production run 2, fixture-load, both seeded runs, both
duplicate-fixture evidence commands, all three comparisons, and postflight
exited 0. Duplicate dbt subprocesses intentionally exited 1 on
`100051 (22012): Division by zero`; their evidence commands verified unchanged
targets and accepted this expected failure. Production/seeded builds passed
their unique/not-null tests (`PASS=5 WARN=0 ERROR=0 SKIP=0 TOTAL=5`).

| Subject/run | Target rows | dbt inserted | dbt updated | Reject export rows |
|---|---:|---:|---:|---:|
| production/1 | 61 | 61 (CTAS readback) | 0 | 3 |
| production/2 | 61 | 0 | 61 | 3 |
| seeded/1 | 11 | 7 | 2 | 7 |
| seeded/2 | 11 | 0 | 9 | 7 |
| dup_within_route/1 | 1 (unchanged) | 0 | 0 | 0 |
| dup_within_route/2 | 1 (unchanged) | 0 | 0 | 0 |

Production run 1 used CTAS, not MERGE: its adapter `rows_affected=1` is a
statement result, not a target-row count. The comparison JSON records zero
MERGE rows for that run; 61 comes from full typed target readback. Other
successful runs' inserted/updated counts come from MERGE RESULT_SCAN.

All four full typed comparisons pass for production and seeded, in both
directions, with no duplicate keys. Duplicate-fixture oracle1/oracle2 and
dbt1/dbt2 pass; oracle/dbt comparisons intentionally differ: the runner performs
two ordered updates while dbt fails closed and retains the initial row.
Raw .bad multisets and typed rejects pass for every subject/run. Branch checks
and runner writer-stat expectations pass. Seeded runner run 1 records 7 inserts
and 3 updates; run 2 records 10 updates. dbt applies only 9 distinct winning
keys, because the STANDARD winner replaces the critical operation for a
cross-route key. These are operation-count differences, not value differences.
PostgreSQL CHAR(12) padding is preserved in typed comparisons, not stripped.

Recovery history reports no foreign target writes from preflight through
recovery; each between-run check reports no intervening target writes. These
checks use current-user INFORMATION_SCHEMA history, not account-wide audit
history, so other users' activity is not independently certified. Production
and fixture target comment readbacks match the required token/expiry. The
fixture schema is preserved for review; no target reset/full refresh was used.

Control preflight query: `01c8539e-030d-21f3-0035-065b001c4242`.
Postflight query: `01c853a4-030d-1e67-0035-065b001a2d72`.
All 20 rows are byte-identical, SHA256
`36035640ebee71b816d4e1a15ba52e1d1c37aef9da577722e0533320a2fe9ab3`.
Final offline regression: `98 passed in 3.80s`.

Evidence index and bundle: `warehouse/parity/out/evidence/unt5/evidence_index.json`
and `warehouse/parity/out/evidence/unt5/bundle.tar.gz`, packaged at the executed
collector commit above; individual execution files retain original provenance.
Within-route duplicate keys deliberately fail closed rather than reproduce
runner last-write semantics. Malformed/untyped inputs are not certified.
