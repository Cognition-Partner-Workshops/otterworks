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
