# UNT-7 role-grant evidence — Step A (offline only)

No Snowflake connection was made in this handoff. Live commands below are
written, NOT executed. XML, runner, harness and UNT-2 through UNT-6 are unchanged.

## Runner-derived contract

Paths below are relative to etl/informatica unless otherwise noted.

| Behavior | Authority and verified contract |
|---|---|
| Dispatch | repository/SFX_CONTENT/mappings/m_SFX_ROLE_GRANT.XML:55-73 connects SQ to EXP directly to one target, without router/filter. Session wf_SFX_CONTENT_DAILY.XML:967-1015 names this mapping. |
| Slicing | engine.py:339-367 dispatches SQ port coercion; engine.py:26-35 slices strings to precision. XML:28-31 specifies 20/20/12/10. Slice precedes expression. |
| NULL | engine.py:369-397 maps empty fields to None; literal '*' is ordinary text, ignoring XML NULL_CHARACTER. |
| Integers | expr.py:618-630 and :749 map TO_BIGINT to integer conversion: strip whitespace, accept signed numeric prefix, truncate decimal toward zero; no bigint bound until writer. Blank/non-numeric/star errors. |
| Role | XML:51; expr.py:555-562 ASCII-space-only trims, UPPER, then engine.py:470-477 output coercion slices to 12 again. Tabs survive. |
| Date | XML:52; expr.py:355-439,655-660 validate explicit YYYY-MM-DD including calendar. Month/day may be one digit. engine.py:63-69 converts target date/time to DATE. Source is sliced to 10 first. |
| Expression errors | ERROR default, engine.py:435-482 drops row; engine.py:191-199 increments failed-source rows. No .bad record. Session XML:1010 Stop on errors=0 permits completion. |
| Writer/truncate | Session XML:981-986 Insert=YES, truncate=YES; :999 Treat source rows as Insert. engine.py:791-818 sets insert default and DELETE FROM before writing. |
| Batch fallback | engine.py:842-876 COPY batches then per-row INSERT on batch failure. NULL key, either bigint overflow and later duplicate keys reject; first insertable key in stream wins. |
| Reject rowtype | expr.py:23 defines DD_INSERT=0 (DD_UPDATE=1). engine.py:835-864 writes unpadded values with rowtype 0 to role_grant1.bad. |
| Readback | bootstrap.sql:416-421 GRANT_ID BIGINT NOT NULL PRIMARY KEY, USER_ID BIGINT, ROLE_CD CHAR(12), GRANTED_DT DATE. Macro pads VARCHAR(12) explicitly, preserving NULL. |
| Replay | Truncation removes every prior row on each session; identical input produces identical multiset, including duplicate first-wins results. |

DD_INSERT resolves to **0**; UNT-6's rowtype 1 belonged to its
update-else-insert path. The runner agrees with the proposed semantics.
dbt table replacement is deliberately atomic rather than reproducing DELETE's
failure window. No incremental merge, reset, truncate or full-refresh is used.
Duplicate non-null candidate keys are a separate **NOT PARITY** subject: source
file order is absent in PC_SRC. A global MAX(count) division guard fails closed.
The reject analysis exposes constraint rejects, not order-dependent duplicates.

## Frozen source

149 rows in tests/fixture/landing/users/ROLE_GRANT/20261109.psv.
SHA256 a833d990104666dfc08d1ab7bcc50b8a4101b3c473e88ae5614e2df9525a1788.
All 149 rows are insertable, with 149 distinct keys, no expression failures,
writer rejects or duplicates. Offline tests enforce these facts.
warehouse/parity/harness.py:72-108 derives PC_SRC DDL from STG_ROLE_GRANT
(bootstrap.sql:422-427): GRANT_ID/USER_ID BIGINT, ROLE_CD VARCHAR(200),
GRANTED_DT DATE. Empty landing fields become NULL. Fixtures retain raw strings.

## Seeded fixture expected fate (1-based input rows)

| Rows | Expected fate |
|---|---|
| 1 | Insert 101/1 ADMIN; replaces seeded key 101, not an update. |
| 2 | Insert mixed-case ASCII-space-trimmed MIXED. |
| 3 | Insert tab-delimited role; tabs survive. |
| 4 | Slice before trim: leading blank plus first 11 letters -> ABCDEFGHIJK. |
| 5 | Insert NULL user, role and date. |
| 6 | Insert literal '*' role, not NULL. |
| 7,8 | Bad key/user expression drops, no .bad. |
| 9,10 | Blank-after-trim key/user expression drops, no .bad. |
| 11 | Decimal key/user truncate toward zero -> 109/9. |
| 12 | Numeric prefixes -> 110/10. |
| 13 | Whitespace and signed integers -> 111/11. |
| 14,15,16 | Key overflow, user overflow, NULL key: writer rejects with rowtype 0. |
| 17,18 | Invalid calendar and wrong format: expression drops. |
| 19 | Overlength date slices to valid 2026-11-09; insert. |
| 20 | Insert negative key and user. |
| 21,22 | Literal '*' key/date: expression drops. |
| 23 | All-space role becomes empty, then CHAR-equivalent 12 spaces. |
| 24 | Overlength key slices to 11912345678901234567, still overflow: writer reject. |
| 25 | One-digit month/day is accepted by runner explicit format; insert. |

25 input = 13 inserts + 4 writer rejects + 8 expression drops.
Session FAILED_ROWS=12 includes both categories; only four lines are in .bad.
Seed 999 disappears entirely and seeded 101 is replaced; both runs repeat.
dup_key contains two inserts of 201; oracle keeps FIRST/user 1, rejects SECOND
with rowtype 0. Both initial keys (201 old, 999) are removed before load.
dbt must fail and preserve both seeds, NOT claim duplicate value/reject parity.

## Local oracle and checks

Results and exact commands/HEAD/exit codes are retained under ignored
warehouse/parity/out/evidence/unt7/checks/. Oracle evidence retains raw
stdout/stderr, session logs, .bad, REP_SESS_LOG, typed snapshots, hashes and
the exact sole startsession command vector. Unique local DBs are dropped
in finally; run 2 has no intervening reset.

| Scenario/run | Target rows | Inserts | Writer rejects | Expression drops |
|---|---:|---:|---:|---:|
| frozen/1,2 | 149 | 149 | 0 | 0 |
| seeded/1,2 | 13 | 13 | 4 | 8 |
| dup_key/1,2 | 1 | 1 | 1 | 0 |

Commands (from warehouse, local PostgreSQL container bound to 127.0.0.1:56417):

```sh
TD_PORT=56417 TD_PASSWORD=postgres .venv/bin/python -m parity.evidence_unt7 oracle --scenario frozen
TD_PORT=56417 TD_PASSWORD=postgres .venv/bin/python -m parity.evidence_unt7 oracle --scenario seeded
TD_PORT=56417 TD_PASSWORD=postgres .venv/bin/python -m parity.evidence_unt7 oracle --scenario dup_key
.venv/bin/python -m pytest parity/tests -q
# Parse twice using inert placeholder profile values, fixture unset then =1.
.venv/bin/dbt parse --project-dir dbt --profiles-dir dbt --no-partial-parse
```

The venv was absent, so created locally from snowflake/requirements.txt plus
sqlglot==28.0.0 and setuptools==80.9.0. No dependency file changed.
Existing marts/billing unused configuration warnings are resource-inventory
warnings, not missing dependencies.

Executed offline results at parent HEAD ed22934c7989adb435e8ca7141f8939841f44d05
with the new implementation in the working tree:
`183 passed, 1 skipped in 5.41s` (142 prior cases plus 42 new).
The skipped case is UNT-6's local-capture test: its uncommitted oracle artifacts
are not present in this checkout. Both fixture-unset and fixture-set dbt parse
exited 0 with dbt 1.9.8 / snowflake adapter 1.9.0, using inert placeholder profile
values and disabled usage telemetry, with no warehouse connection.
The first test attempt exposed a missing types field in a new synthetic test
snapshot; that test helper was corrected. Both attempt logs are retained.
Local oracle lineage hashes preserve the exact capture-time working tree;
subsequent test-helper and documentation edits are bound separately in packaging.

## Coordinated live sequence — written, NOT executed

```sh
.venv/bin/python -m parity.evidence_unt7 preflight
.venv/bin/python -m parity.evidence_unt7 fixture-load
# For each subject: production, seeded, dup_key, in that order:
.venv/bin/python -m parity.evidence_unt7 run --subject seeded --run 1
.venv/bin/python -m parity.evidence_unt7 run --subject seeded --run 2
.venv/bin/python -m parity.evidence_unt7 compare --subject seeded
.venv/bin/python -m parity.evidence_unt7 postflight
.venv/bin/python -m parity.evidence_unt7 index
```

Preflight is read-only, refuses any existing production ROLE_GRANT target
(even empty) and any existing fixture schema, validates full frozen source
and optional PC_BEFORE. Fixture-load creates only new commented objects in
PC_FX_UNT7_ROLE_GRANT, with verified typed seeds/raw input readbacks.
generate_schema_name.sql returns the custom schema unchanged, so no prefix
is added. Fixture models enable only with SFX_UNT7_ROLE_FIXTURE=1.
Every build selects exactly one model; every connection/build tags mapping
m_SFX_ROLE_GRANT and run sfx-d1110 via the existing connector.
All 20 control rows plus SHA and full typed protected snapshots are retained,
checked before builds and postflight: STG_APP_USER, APP_USER, STG_DOCUMENT,
DOCUMENT, DOC_SHARE and PC_CONTENT.LOGIN_EVENT. No source, control, before or
protected table is written. No grants issued.

No act-3 or DOC_SHARE dbt model is present in this checkout's warehouse/dbt.
A recursive SQL search finds ROLE_GRANT references only in the new UNT-7
macro/models/analysis. Thus no existing dbt model here reads PC_CONTENT.ROLE_GRANT;
this does not assert anything about deployed external/generated models.

Limits: no Snowflake SQL execution, table replacement atomicity or runtime guard
certification in Step A. Arbitrary Unicode digits/whitespace/case conversions
remain untested. Typed production sources cannot represent malformed strings.
History is current-user only, not an independent account-wide writer audit.
Duplicate subject is explicitly NOT PARITY. No UI surface was changed.

## Step B live results — 2026-11-10

Production builds executed at `0607eba02ad7e700ccb23415de602be12956ad4a`.
Seeded and dup_key builds executed at
`6f052a157b7717cca41129db26ce38827527f9a7`, after the separately approved
collector-only fix, "Count only successful statements as intervening writes".
No dbt macro, model, analysis, YAML, PSV fixture, mapping configuration, oracle,
runner, bootstrap, parameter or XML input changed between these executed HEADs.
The final follow-up commit appends only this section. Packaging binds both
executed HEADs to the final HEAD with per-file SHA256s and explicitly records
the collector and test changes. JWT key material stayed in memory.

### Guarded chronology and the retained failed comparison

Read-only preflight verified absent production target and fixture schema,
149/149 matching frozen source rows, and PC_BEFORE.ROLE_GRANT matching all 149
local oracle rows. Fixture-load created only the approved new fixture schema
and its four commented tables. Production builds 1/2 succeeded without rebuilds.

An auxiliary readback used the reserved alias ROWS and failed compilation:
QID `01c853cc-030d-1e7f-0035-065b001bb81e`, error 001003,
"syntax error line 1 at position 19 unexpected 'ROWS'." Its corrected read-only
query used N_ROWS and returned 149 rows / 149 distinct GRANT_IDs.
Snowflake classified the failed SELECT as UNKNOWN / FAILED_WITH_ERROR, so the
original conservative comparison incorrectly reported an intervening write.
All value, reject and writer-count comparisons already matched.

Execution stopped for approval. The approved collector change counts only
EXECUTION_STATUS=SUCCESS statements as intervening writes, and retains failed
statements separately with QID, error code and message. A failed Snowflake
statement is atomic and writes nothing; that failed SELECT changed no data.
Original production/comparison.json and production/between_runs files remain
byte-for-byte unchanged. Their before/after SHA256s are recorded in
production/comparison_attempts/52134f52efa940ccb2ff9856d1c51460/comparison.json.
The read-only comparison retry passed; no production build was repeated.

Continuation records bind the preflight HEAD to the new executed HEAD and allow
only evidence_unt7.py and test_evidence_unt7.py changes. Every other hashed file
must match; all source, control, protected-table and initial-target gates remain.
Offline classifier/preservation/continuation tests reported
`187 passed, 1 skipped in 4.50s` before the classifier commit.

Seeded runs 1/2, compare, dup_key runs 1/2, compare and postflight all completed.
The duplicate dbt subprocesses exited 1 as expected; their evidence commands
exited 0 after verifying division-by-zero errors and full initial-row preservation.
All exact outer argv vectors, raw stdout/stderr, UTC start/end times and HEADs
are retained in chronology and each run's execution.json; the actual run_dbt.py
build argv vectors are collected in chronology/actual_dbt_invocations.json.
The initial orchestration attempt resolved the venv Python symlink to system
Python and failed before a connection; that failed invocation is retained too.

### Results

| Subject/run | Target rows | Rejects | Oracle minus dbt | dbt minus oracle | Result |
|---|---:|---:|---:|---:|---|
| production/1 | 149 | 0 | 0 | 0 | PARITY |
| production/2 | 149 | 0 | 0 | 0 | PARITY |
| seeded/1 | 13 | 4 | 0 | 0 | PARITY |
| seeded/2 | 13 | 4 | 0 | 0 | PARITY |
| dup_key/1 | 2 unchanged | 0 | 1 | 2 | NOT PARITY; expected guard failure |
| dup_key/2 | 2 unchanged | 0 | 1 | 2 | NOT PARITY; expected guard failure |

These are strict typed bidirectional multiset differences with multiplicities,
not EXCEPT DISTINCT counts. Production and seeded values/keys are stable across
runs, including CHAR-equivalent padding and NULLs. Seeded oracle has eight
expression drops and four writer rejects, not twelve .bad rows; raw and typed
reject exports agree on both runs. Seed 999 disappears and input 101 replaces
its old seeded value. Duplicate oracle retains FIRST/user 1 and rejects SECOND;
dbt keeps both original seeded rows, rather than choosing an unordered winner.

Four successful builds report `Done. PASS=5 WARN=0 ERROR=0 SKIP=0 TOTAL=5`.
Both duplicate builds report `100051 (22012): Division by zero` and
`Done. PASS=2 WARN=0 ERROR=1 SKIP=2 TOTAL=5`. Full snapshots certify their
failure leaves the initial target intact. Duplicate value/reject parity is
intentionally not asserted.

| Subject/run | Model statement QID | run_results invocation_id |
|---|---|---|
| production/1 | 01c853cb-030d-1e77-0035-065b001a6f8e | db8e4ae5-f48d-4e6b-98da-09665bd6f9b1 |
| production/2 | 01c853cd-030d-1e7d-0035-065b001a5fda | e88d646c-3f49-470c-a937-e6cfdb223b85 |
| seeded/1 | 01c853d0-030d-1e6e-0035-065b00199f42 | c05e7634-83d6-4e8f-90b6-f4fc67f478bf |
| seeded/2 | 01c853d0-030d-1e6e-0035-065b00199f62 | 9118cf2f-e733-410e-8ed0-800243688e48 |
| dup_key/1 | 01c853d1-030d-1e67-0035-065b001a2e72 | 9bf951b5-17d7-4f0f-a91d-b9eb1fb0dc72 |
| dup_key/2 | 01c853d2-030d-1e72-0035-065b0019bff6 | 539a4785-7b80-4cc7-af65-8fbcb77174fe |

### Table recreation, not object-identity replay

Actual model statements are CREATE OR REPLACE TRANSIENT TABLE AS SELECT, not
MERGE. SHOW TABLES and INFORMATION_SCHEMA.TABLES confirm transient objects.
Production SHOW/readback after both runs certifies 149 rows and 149 distinct
GRANT_IDs, with full row snapshots retained.

| Relation | CREATED after run 1 / before run 2 (UTC) | CREATED after run 2 (UTC) |
|---|---|---|
| PC_CONTENT.ROLE_GRANT | 2026-11-10 23:07:54.744 | 2026-11-10 23:09:08.951 |
| PC_FX_UNT7_ROLE_GRANT.UNT7_FIXTURE_SEEDED | 2026-11-10 23:12:02.169 | 2026-11-10 23:12:43.026 |

These independent SHOW/INFORMATION_SCHEMA observations and successful replacement
QIDs prove recreation on each successful build. Row keys and values are stable;
the object is recreated, not identity-preserved, as the chosen truncate-and-load
equivalent. Numeric TABLE_ID changes are not directly certified: ACCOUNT_USAGE
TABLES was queried twice but had not exposed these new objects yet.
INFORMATION_SCHEMA.TABLES and SHOW TABLES expose CREATED, not a TABLE_ID column.
No unsupported TABLE_ID query or metadata mutation was attempted. The fixture
schema remains available for review.

### Control, protected tables and write-scope proof

All 20 control rows (8 migrations-page / 12 act3-workflow) are byte-identical:
pre/post SHA256
`36035640ebee71b816d4e1a15ba52e1d1c37aef9da577722e0533320a2fe9ab3`.
Protected aggregate pre/post SHA256:
`47c1cf166f3e4874b2a124844e1d5f80dd7dad8c26f50cc65693b34ba79b6396`.
Full sorted typed snapshots match for STG_APP_USER 126, APP_USER 126,
STG_DOCUMENT 155, DOCUMENT 154, DOC_SHARE 164 and LOGIN_EVENT 412.
Per-table pre/post SHA256s are in postflight_audit/protected_tables.json.

The current-user run/mapping-tagged history capture contains 511 queries,
33 successful durable DML/DDL/comment/tag statements, 26 session-setting
statements, and zero unparsed successful non-read targets. Durable write targets:

- PC_CONTENT.ROLE_GRANT
- PC_FX_UNT7_ROLE_GRANT (schema creation)
- PC_FX_UNT7_ROLE_GRANT.SEEDED_SOURCE
- PC_FX_UNT7_ROLE_GRANT.DUP_KEY_SOURCE
- PC_FX_UNT7_ROLE_GRANT.UNT7_FIXTURE_SEEDED
- PC_FX_UNT7_ROLE_GRANT.UNT7_FIXTURE_DUP_KEY

No __DBT_TMP object was needed by this table materialization. Comments finalized
to run_token=sfx-d1110 expires=2026-11-24. No write targets PC_SRC, PC_BEFORE,
PC_AUDIT, LOGIN_EVENT, an act-3 table, PC_BILLING or MIGRATION_CONTROL; no grant,
task execution, setup/global load, truncate, reset, full-refresh or restore ran.
Between-run history has no successful intervening target writes. The failed
auxiliary SELECT and both expected failed duplicate statements are retained
with their QIDs/errors, not erased or counted as writes.

Final read-only activity check found zero other running/queued/blocked tagged
UNT-7 queries; connections closed and no local dbt/evidence subprocess remained.
Limits: history is current-user tagged history, not an account-wide audit of
other-user or untagged writes; arbitrary Unicode conversions remain unexercised;
dup_key remains NOT PARITY; numeric TABLE_ID changes remain unavailable.
NO CI RAN. Final-HEAD offline tests and both inert-profile dbt parses are recorded
separately under checks_final, with HEAD, argv and exit codes.

Packaging: evidence_index.json, bundle.tar.gz (all raw evidence),
checks_logs.tar.gz and implementation_binding.json bind the two executed HEADs
to the final documentation HEAD. The binding proves all dbt implementation and
oracle/runner/XML inputs identical while explicitly listing the approved
collector/test hash changes; only documentation changes after the fixture builds.
