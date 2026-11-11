# UNT-6 login-event evidence

The Step A record below describes implementation, offline tests and local
PostgreSQL captures. Step B live results follow and supersede its historical
not-yet-certified Snowflake limitations.
The XML, runner, shared harness and UNT-2 through UNT-5 files are unchanged.

## Frozen production input (checked before implementing semantics)

The harness source_plan/ setup uses
`etl/informatica/tests/fixture/landing/users/LOGIN_EVENT/20261109.psv`,
not the unrelated header-bearing RAW_USERS Snowflake scaffold fixture.
There are 420 rows, SHA256
`cb4dcd0bc149bcdaaebe6e3001a1e3e1c3e355685f6bc028d57b22631610cb54`.
SUCCESS: 364; FAILED: 38; LOCKED: 3; MFA_FAILED: 7; TIMEOUT: 8.
Thus SUCCESS receives 364, FAILURE 48, DEFAULT1 8.
There are no within-route duplicate LOGIN_IDs, no keys shared across routes,
no empty or literal-star fields, and no invalid or out-of-bigint-range numeric
or invalid timestamp fields. PC_SRC loses file order, but this input does not
require within-route ordering.

`harness.py:72-108` derives source DDL from bootstrap STG_LOGIN_EVENT:
LOGIN_ID/USER_ID BIGINT, LOGIN_TS TIMESTAMP(0), RESULT_CD/CLIENT_TYPE VARCHAR(200).
COPY maps empty fields to NULL, not `*`. The production macro accepts these typed
columns; isolated fixture sources retain raw strings to exercise conversions.

## Runner-derived semantics

| Behavior | Actual contract and authority |
|---|---|
| Input precisions | SQ string slicing 20/20/19/12/12 before expression, engine.py:26-35,339-367; XML SQ ports |
| Landing NULL | Empty field becomes None; literal `*` is ordinary text despite XML NULL_CHARACTER, engine.py:369-397 |
| TO_BIGINT | NULL stays NULL; strips whitespace, accepts signed numeric prefix, truncates decimal toward zero. Blank/non-numeric/`*`/`.5` errors; no bigint bound at expression time, expr.py:618-630,749 and engine.py:26-59 |
| TO_DATE | NULL stays NULL; explicit format parser validates calendar/time, expr.py:355-439,655-660 |
| ERROR default | Drops expression-error row and increments FAILED_SOURCE_ROWS. No .bad record. Stop on errors=0, so session succeeds, engine.py:191-199,435-482; session XML:1073 |
| Trimming/case | Slice first, ASCII-space-only LTRIM/RTRIM then UPPER, output precision 12; tabs survive, expr.py:555-562; engine.py:470-477 |
| Router | SUCCESS to writer 1, FAILED/LOCKED/MFA_FAILED to writer 2. Other values including NULL go DEFAULT1. No DEFAULT1 connectors, so silently dropped, not DD_REJECT, engine.py:665-697; mapping XML:64-119 |
| Writer | Treat source rows as Update; update-else-insert, no truncate, engine.py:791-818,866-910; session XML:1016-1073 |
| Writer rejects | NULL key and key overflow fail UPDATE with rowtype 0. Valid missing key with USER_ID overflow gets to INSERT and rejects with rowtype 1. Values unpadded in .bad, engine.py:835-864,883-898 |
| Ordering | SUCCESS finishes before FAILURE, so cross-route key has FAILURE value. Pending inserts flush before next update, so within-route duplicates are ordered last-write-wins, mapping XML:120-121; engine.py:866-899 |
| Readback | PostgreSQL CHAR(12) pads; Snowflake VARCHAR(12) explicitly RPADs. NULL remains NULL, empty remains distinct. No whitespace normalization in full_compare. |

The local seeded capture disproved an initially overly broad reject-rowtype
assumption: USER_ID overflow with a valid absent key emits **1**, not 0.
The failed first capture is retained as `oracle/seeded_failed_reject_classifier`.
Successful captures use the corrected collector; each lineage retains its own
commit and implementation hashes. No historical capture was overwritten.

## Fixtures and oracle results

Seeded has 28 input rows: SUCCESS 11, FAILURE 6, DEFAULT 5, expression-error 6.
It covers every code, NULL result, mixed case/spaces/tabs, overlength strings,
NULL key in both writers, NULL user/timestamp/client, bad bigint/date/star,
decimal and numeric-prefix bigint, both key/user overflow, seed updates,
rejected/default seed preservation, an untouched seed and a cross-route key.

| Scenario/run | Target rows | SUCCESS inserts/updates | FAILURE inserts/updates | .bad rows | Expression failures |
|---|---:|---:|---:|---:|---:|
| frozen/1 | 412 | 364/0 | 48/0 | 0 | 0 |
| frozen/2 | 412 | 0/364 | 0/48 | 0 | 0 |
| seeded/1 | 14 | 8/1 | 3/1 | 4 | 6 |
| seeded/2 | 14 | 0/9 | 0/4 | 4 | 6 |
| dup_within_route/1 | 1 | 0/2 | 0/0 | 0 | 0 |
| dup_within_route/2 | 1 | 0/2 | 0/0 | 0 | 0 |

All six successful runner sessions report SUCCEEDED, with no resets between runs.
Seeded FAILED_ROWS=10 consists of six expression failures plus four writer rejects,
not ten .bad rows. DEFAULT contributes neither. Cross-route key 112 ends LOCKED
with user 13. Duplicate key 201 ends with user 2 on both runs.

Within-route duplicates are a separate **NOT PARITY** subject: the runner accepts
ordered updates, but dbt fails closed before MERGE/CTAS using the shared global
division guard. There is no production duplicate tie-break choice to approve.
Step B must prove the guard errors atomically and preserves the seed.

## Commands and evidence

From warehouse, in its venv, with a throwaway PostgreSQL container bound only to
127.0.0.1:56416:

```sh
TD_PORT=56416 .venv/bin/python -m parity.evidence_unt6 oracle --scenario frozen
TD_PORT=56416 .venv/bin/python -m parity.evidence_unt6 oracle --scenario seeded
TD_PORT=56416 .venv/bin/python -m parity.evidence_unt6 oracle --scenario dup_within_route
```

Only s_m_SFX_LOGIN_EVENT runs in each unique temporary local database. Databases
are dropped in finally; input bytes, initial/input/target typed snapshots, hashes,
lineage, stdout/stderr, session logs, REP_SESS_LOG, raw .bad and writer counts
remain in ignored `warehouse/parity/out/evidence/unt6/`.

The warehouse venv was absent in this worktree. It was created locally and
installed from warehouse/snowflake/requirements.txt plus sqlglot==28.0.0;
no dependency files changed. Check logs include HEAD, exact command and exit
code under `out/evidence/unt6/checks/`.

Offline checks at parent HEAD 2116dd9d90a40be2180330d0f1e2b396614092d9
with the new implementation in the working tree:
`142 passed in 4.08s` (98 existing plus 44 new cases).
Both fixture-unset and fixture-set dbt parse exited 0 using dbt 1.9.8 and
snowflake adapter 1.9.0. Both report only the existing unused marts/billing
configuration paths. The content configuration is now used. These warnings
are project resource inventory warnings, not missing environment dependencies.

### Coordinated live sequence — written, NOT executed

```sh
.venv/bin/python -m parity.evidence_unt6 preflight
.venv/bin/python -m parity.evidence_unt6 fixture-load
# For each subject: production, seeded, dup_within_route
.venv/bin/python -m parity.evidence_unt6 run --subject seeded --run 1
.venv/bin/python -m parity.evidence_unt6 run --subject seeded --run 2
.venv/bin/python -m parity.evidence_unt6 compare --subject seeded
.venv/bin/python -m parity.evidence_unt6 postflight
.venv/bin/python -m parity.evidence_unt6 index
```

Preflight is read-only and refuses unexpected nonempty production initial state,
compares full frozen input, and optionally cross-checks PC_BEFORE. It never resets.
Fixture-load refuses an existing PC_CONTENT_UNT6_FIXTURE schema, creates only
commented objects in that schema, loads oracle input/seed and checks readback.
Fixture models are enabled only by SFX_UNT6_LOGIN_FIXTURE=1 and configure their
schema inline. Builds select exactly one model, never parents/descendants and
never full-refresh. Only PC_CONTENT.LOGIN_EVENT and fixture objects may be
written; PC_SRC, PC_BEFORE, MIGRATION_CONTROL and other production tables are
read-only. No grants are issued.

All warehouse connections/builds carry JSON QUERY_TAG run=sfx-d1110 and
mapping=m_SFX_LOGIN_EVENT. Object comments are finalized to
`run_token=sfx-d1110 expires=2026-11-24` by existing PC hooks. Governance hooks
tag only selected successful built relations; incremental adapter temporary
views and metadata/session statements follow the existing UNT-5 adapter behavior.
Snowflake sessions use QUERY_TAG, not an unsupported session COMMENT parameter.

Pre/postflight capture all 20 control rows plus SHA and require byte-identical
snapshots. Before each build, HEAD/implementation, input, initial target and
control gates must pass. Compare retains strict typed full multisets, raw and
typed rejects, key multiplicity, writer/merge counts and between-run history.
Query history is current-user, not an independent account-wide writer audit.

Not yet certified: any Snowflake SQL runtime behavior, Snowflake duplicate
guard atomicity, raw-string conversions beyond the exercised fixtures (including
Unicode digit/whitespace differences), and concurrent foreign writers.
Production PC_SRC is typed and cannot preserve malformed numeric/date strings.
The duplicate subject must never be presented as oracle/dbt value parity.

## Step B live results — 2026-11-10

All live commands executed at
`9956fea7c160a038908b7d63629915c43241f8af`.
No implementation fixes were required. The follow-up commit changes only this
document; model/macro/fixture/evidence implementation hashes remain identical.
Final-HEAD offline check logs and packaging provenance are retained separately.
JWT keys stayed in memory and were never printed or saved.

### Guarded chronology

1. Read-only preflight guards captured session ID, user, QUERY_TAG, control,
   target absence, fixture-schema absence and full act-3 table snapshots.
2. Preflight confirmed 420/420 typed source rows, zero multiset differences,
   absent production target, and PC_BEFORE 412/412 matching the local runner.
3. Fixture-load created only the new commented fixture schema and its four
   tables, then verified raw input and seed readbacks.
4. Production run 1 CTAS, production run 2 MERGE, comparison; seeded runs 1/2
   MERGE, comparison; duplicate runs 1/2 expected failed MERGE, comparison.
   Every evidence command exited 0; the two duplicate dbt subprocesses exited 1.
5. Postflight control and five act-3 snapshots were byte-identical. Current-user
   tagged query history captured the full write window.
6. Additional read-only shared-macro checks proved the entire 420-row production
   input after expressions matched the runner in both directions (0/0), and
   counted exactly six seeded expression drops.

Exact subprocess argument vectors, executed HEAD and UTC times are in
`chronology/*.json` and each run's `execution.json`. The actual recorded
`run_dbt.py` invocations are preserved in
`chronology/actual_dbt_invocations.txt`; they are not inferred from dbt logs.
All paths in this section are relative to `out/evidence/unt6/`.

### Results

| Subject/run | Target | Rejects | Oracle minus dbt | dbt minus oracle | dbt insert/update |
|---|---:|---:|---:|---:|---:|
| production/1 | 412 | 0 | 0 | 0 | 412/0 CTAS readback |
| production/2 | 412 | 0 | 0 | 0 | 0/412 |
| seeded/1 | 14 | 4 | 0 | 0 | 11/1 |
| seeded/2 | 14 | 4 | 0 | 0 | 0/12 |
| duplicate/1 | 1 unchanged | 0 | 1 | 1 | 0/0 — NOT PARITY |
| duplicate/2 | 1 unchanged | 0 | 1 | 1 | 0/0 — NOT PARITY |

EXCEPT-direction counts above are strict typed multiset differences, including
multiplicities, calculated offline from full Snowflake and oracle snapshots.
They are not merely SQL EXCEPT DISTINCT counts. Production and seeded have no
duplicate LOGIN_IDs and byte-equivalent typed values across runs. Seed row 104
is preserved with user 92 and both padded UNTOUCHED strings. Raw .bad line
multisets and typed reject exports agree on both seeded runs. Six expression
errors are dropped before routing; they do not appear in the four writer rejects.

All four successful builds report
`Done. PASS=5 WARN=0 ERROR=0 SKIP=0 TOTAL=5`.
Both duplicate MERGEs fail with `100051 (22012): Division by zero`,
and full target snapshots prove atomic seed preservation. Their 1/1 differences
from the ordered-update oracle are intentional, not parity.
No truncate, reset or full-refresh was used.

| Subject/run | Model statement QID | run_results invocation_id |
|---|---|---|
| production/1 | 01c853b6-030d-1e5e-0035-065b001a3f3a | 3b98cf56-1cb2-4a39-9f71-0e085821d5b0 |
| production/2 | 01c853b6-030d-2214-0035-065b001c5316 | ccb88285-1618-44f0-acc3-0c9b945a6d70 |
| seeded/1 | 01c853b7-030d-1e75-0035-065b0019dd5a | 8db08735-3a17-4d75-988c-5982cfff1322 |
| seeded/2 | 01c853b7-030d-1e64-0035-065b0019fdc2 | f25ae225-a0b3-4aac-a867-7c0dfbad4e69 |
| duplicate/1 | 01c853b8-030d-1e5d-0035-065b001a8ea6 | a8ce8b75-e52c-4fa9-882a-b99e3a8892a0 |
| duplicate/2 | 01c853b8-030d-1e73-0035-065b001a9ef2 | 20060953-5868-4c5a-b429-da4c5d270b5b |

### Control and no-touch proof

Control preflight QID: `01c853b5-030d-1e63-0035-065b001a7e3a`.
Postflight QID: `01c853b9-030d-1e75-0035-065b0019dd86`.
Both have 20 rows, 8 migrations-page / 12 act3-workflow, byte-identical SHA256:
`36035640ebee71b816d4e1a15ba52e1d1c37aef9da577722e0533320a2fe9ab3`.

Full sorted typed act-3 snapshots were byte-identical, not just row counts:
STG_APP_USER 126, APP_USER 126, STG_DOCUMENT 155, DOCUMENT 154, DOC_SHARE 164.
Per-table before/after SHA256 values are in
`preflight_guards/act3_tables.json` and `postflight_audit/act3_tables.json`.

History retained 304 run/mapping-tagged queries, with 50 write/transaction
candidates and zero unparsed nontransaction targets. Durable DML/DDL targets:

- PC_CONTENT.LOGIN_EVENT
- PC_CONTENT_UNT6_FIXTURE (schema creation)
- PC_CONTENT_UNT6_FIXTURE.SEEDED_SOURCE
- PC_CONTENT_UNT6_FIXTURE.DUP_WITHIN_ROUTE_SOURCE
- PC_CONTENT_UNT6_FIXTURE.UNT6_FIXTURE_SEEDED
- PC_CONTENT_UNT6_FIXTURE.UNT6_FIXTURE_DUP_WITHIN_ROUTE

The adapter additionally creates/drops session-temporary source views:
PC_CONTENT.LOGIN_EVENT__DBT_TMP and fixture
UNT6_FIXTURE_SEEDED__DBT_TMP / UNT6_FIXTURE_DUP_WITHIN_ROUTE__DBT_TMP.
These are the expected dbt incremental implementation, not additional durable
production tables. Governance comments/tags target only the built relations.
No history target is PC_SRC, PC_BEFORE, MIGRATION_CONTROL, another production
table, a grant, or a warehouse mutation.

Every retained history row includes QUERY_TAG and SESSION_ID; evidence-query
records include SQL and QIDs. Session parameter readbacks are also retained for
the guard/audit sessions. Coverage is current-user INFORMATION_SCHEMA history,
filtered by run/mapping and bounded from preflight through postflight; it does
not independently rule out other-user or untagged writes. Between-run checks
found no intervening target writes. ACCESS_HISTORY was not queried.

The fixture schema is **left in place**, following UNT-5's preserved-for-review
precedent. Remaining limits are unexercised arbitrary raw strings/Unicode
conversions and account-wide concurrent-writer auditing. The duplicate subject
remains NOT PARITY by contract.

Packaging: `evidence_index.json`, `bundle.tar.gz`,
`checks_logs.tar.gz` and `implementation_binding.json` bind the final packaging
HEAD to the executed implementation hashes, while individual captures preserve
their original executed HEAD. Final offline logs live in `checks_final/`.
