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
