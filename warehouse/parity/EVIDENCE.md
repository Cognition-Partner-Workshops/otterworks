# migrations-page evidence (UNT-2)

## UNT-3 audit mapping successor

`parity.evidence_unt3` owns only `m_SFX_STG_AUDIT_EVENT` and
`m_SFX_AUDIT_EVENT`, selected by `mappings/sfx_audit.yml`. Its read-only
`preflight` freezes full PC_SRC rows, both PC_BEFORE readbacks, control rows and
initial PC_AUDIT relation metadata. All evidence is under `out/evidence/unt3`;
each phase retains SQL/QIDs in `queries.json` and `transcript.txt`. Only `run`
invokes dbt; preflight/postflight/replay never issue writes. Do not run `run`
until exclusive target access is coordinated. No full-refresh is used.

The accepted manifest SHA256 is
`b5e0c8a390fba31c4f5f4b930d82d54102eb09e8e35837c90f1096168b67c41c`.
`oracle1` is `unt2_oracle_d53b0b939dd5`, not oracle2 (another oracle execution,
not dbt). Superseded oracle run directories are never selected. The immutable
manifest, implementation file hashes, oracle session lineage/status and full
input rows are checked, not merely row counts.

### Exact semantics and representations

- STG: canonical session truncate YES / Insert, XML lines 597/610; dbt table
  replacement. AUDIT_EVENT: XML lines 640-655 says Update else Insert YES,
  truncate NO and Update. Incremental merge on EVENT_ID updates every non-key
  column and inserts missing keys, preserving unrelated existing target rows.
  This is runner/engine.py:791-818,866-899, not truncate+insert. Initial target
  must be absent or empty; a populated initial AUDIT_EVENT stops before writes.
- Duplicate source EVENT_IDs are never deduped. Runner flushes pending inserts
  before each update (engine.py:880-899), so repeated keys are sequential
  last-write-wins, including a key initially absent. Snowflake MERGE with duplicate
  matches is not equivalent; the evidence run checks the complete STG input
  equals oracle1 and has no duplicate keys before either audit merge. Preflight
  reports duplicate counts on the frozen input and both oracle readbacks.
- String SQ coercion slices before expression evaluation
  (engine.py:26-35,339-367). EVENT_TYPE is sliced to 12 and DETAILS to 160 before
  trimming. Expression output coercion also enforces 12/160 on AUDIT_EVENT
  (engine.py:450-482). Target varchar is not itself sliced by `db_value`
  (engine.py:63-76); database types enforce target widths. No columns excluded.
- `IIF` missing else for bigint is 0, not NULL, including NULL > 0:
  expr.py:924-931,960-973 and truthy at 266-275. Thus both nonpositive/null
  DOCUMENT_ID and CUSTOMER_ID produce 0. Comparisons with NULL produce NULL,
  then the IIF condition treats it as false. `||` treats NULL as empty except
  both operands NULL (expr.py:697-700). The fallback DETAILS includes the literal
  ` by user `, even with null EVENT_TYPE/ACTOR_USER_ID. TO_CHAR(bigint) uses its
  unformatted integer string (expr.py:647-652,327-337). TRIM defaults to spaces
  only; NULL remains NULL, empty remains empty (expr.py:555-562,730-734).
- File NULL_CHARACTER `*` is ignored by the runner: the actual file reader
  makes only empty fields NULL (engine.py:369-397); a literal `*` remains a
  string. Shared PC_SRC uses bootstrap STG types and COPY with
  EMPTY_FIELD_AS_NULL TRUE / NULL_IF empty (parity/harness.py:75-108), so the
  same empty/null representation is already present. Bigints and timestamps
  are already typed; numeric/date conversion failures cannot occur on this
  frozen input. TRY_ predicates are retained in the SQL and reused verbatim by
  read-only reject exports. This is not certification of arbitrary malformed
  landing strings: runner TO_BIGINT even accepts a numeric prefix and truncates
  decimals toward zero (expr.py:618-630); typed PC_SRC cannot retain such strings.
- ERROR defaults do not substitute values: transformation failures increment
  failed source rows and drop the row (engine.py:191-199,435-482). Contrary to
  generic reject-file expectations, only writer rejects emit `.bad` records
  (engine.py:835-840); empty `.bad` files are removed (914-915). Both accepted
  oracle sessions must have zero failed source/target rows. Reject export is a
  full typed input-row multiset selected with the model's exact predicate;
  empty raw oracle `.bad` translates unambiguously to an empty typed multiset.
  Nonempty raw oracle rejects fail closed rather than inventing a lossy decoding.
  There are no Snowflake reject tables.
- Explicit NUMBER(38,0), TIMESTAMP_NTZ(0) and VARCHAR(200/160/12) casts represent
  the oracle bigint/timestamp(0)/varchar/char columns. PostgreSQL char(12) pads;
  Snowflake CHAR does not, so RPAD is representation-only, preserving all spaces.
  DESCRIBE validates actual warehouse types before metadata is mapped to oracle
  type descriptors using `evidence_live.fetched(source_loading=True)` for dbt
  outputs; PC_BEFORE uses its established TIMESTAMP_NTZ(9) storage translation.
  No decimal scale, null/empty, timestamp value or whitespace is normalized away.

### Build side effects (selection without parents or descendants)

`run_dbt.py build --select pc_audit__stg_audit_event` builds that single table
and its warning-only duplicate test. Source PC_SRC.AUDIT_EVENT is SELECT-only.
The installed dbt-snowflake 1.9.0 table materialization directly issues
CREATE OR REPLACE TRANSIENT TABLE STG_AUDIT_EVENT AS (the model SELECT), not an
intermediate/backup rename sequence. It may create the PC_AUDIT schema if absent; dbt also
issues session/query-tag and relation-cache metadata statements. No downstream
AUDIT_EVENT model is selected. Test failure SELECTs do not store rows by default.
Persist-docs and the PC post-hook comment on the built table. On-run-end
`reapply_governance(results)` writes ONLY successful built relations:
`ALTER TABLE SFX_D1110_AFTER.PC_AUDIT.STG_AUDIT_EVENT SET TAG
SFX_D1110_AFTER.GOVERNANCE.SFX_RUN = 'sfx-d1110'`, then COMMENT with the model
description. No policy attachments apply (`governance_policies: {}`).
`pc_finalize_comments(results)` rewrites ONLY that table's comment to
`run_token=sfx-d1110 expires=2026-11-24`. Tag-setting is a write on our relation,
not on other tables. No control, PC_BEFORE, RAW/CORE/MART, or other PC relations
are written. Exact adapter SQL should be retained from the tagged query history
when builds are authorized. STG has no temporary/backup relation on this adapter;
the incremental audit source view is named AUDIT_EVENT__dbt_tmp.

The incremental audit build initially creates its table if absent. Subsequent
runs create a temporary source view, DESCRIBE source/target columns, then MERGE
on EVENT_ID, updating all columns (including the unchanged key) and inserting
missing rows; the temporary view is dropped. Hooks apply only to AUDIT_EVENT.

### Commands after access coordination

From `warehouse/`, with existing in-memory JWT secret bindings:

```sh
.venv/bin/python -m parity.evidence_unt3 preflight
.venv/bin/python -m parity.evidence_unt3 run --mapping m_SFX_STG_AUDIT_EVENT --run 1
.venv/bin/python -m parity.evidence_unt3 run --mapping m_SFX_STG_AUDIT_EVENT --run 2
.venv/bin/python -m parity.evidence_unt3 replay --mapping m_SFX_STG_AUDIT_EVENT
.venv/bin/python -m parity.evidence_unt3 run --mapping m_SFX_AUDIT_EVENT --run 1
.venv/bin/python -m parity.evidence_unt3 run --mapping m_SFX_AUDIT_EVENT --run 2
.venv/bin/python -m parity.evidence_unt3 replay --mapping m_SFX_AUDIT_EVENT
.venv/bin/python -m parity.evidence_unt3 postflight
```

Do not recapture preflight over existing initial-state evidence. Each `run` uses
a UUID query-tag step and preserves combined raw stdout/stderr, dbt log,
run_results adapter responses, tagged query history SQL/QIDs and UTC execution
bounds. No resets, full-refreshes or source changes between run1 and run2.

The local commands never connect to Snowflake. Live commands use the existing JWT
connector with an in-memory key and never write control rows.
HARNESS self-tests and two fresh oracle executions are **not mapping parity**.
The canonical XML and runner remain unchanged. `scope()` expands the owned config
with folder/workflow/session/targets, reject filenames, parameters, disabled-task
reasons and sequence initial values from canonical exports; the manifest records
that full resolved configuration.

## UNT-4 audit daily summary and archive

Scope: `m_SFX_AUDIT_DAILY_SUMMARY` -> `PC_AUDIT.AUDIT_DAILY_SUMMARY` and
`m_SFX_AUDIT_EVENT_ARCHIVE` -> `PC_AUDIT.AUDIT_EVENT_ARCHIVE`, built on UNT-3
(`PC_AUDIT.AUDIT_EVENT`, unchanged and re-verified row-for-row before every run).
Executed candidate b64d903a35c4af58a53f78b50fd0346a97cef8b0. `evidence_unt4.py` refuses to
run if HEAD or any implementation file hash changes after preflight.

Summary: `AGG_DAILY_EVENTS` groups by `TRUNC(EVENT_TS,'DD')` and `CUSTOMER_ID`.
`SEQ_AUDIT_SUMMARY` starts at 50001. The runner numbers groups in the order it
first sees them, which is EVENT_ID order for the audit target. Ranking the
accepted UNT-2 oracle's groups by `MIN(EVENT_ID)` reproduces all 118
SUMMARY_IDs, so the model uses that ordering. **Intended difference:** the
legacy session is Insert with no truncate, so a rerun appends 118 duplicate
groups with new IDs (`tests/test_runner_integration.py`). dbt instead MERGEs on
SUMMARY_ID. Existing groups keep their IDs (run 2 rewrites the 118 matched rows
with identical values), and new groups continue from MAX(SUMMARY_ID)+1.
First-load parity includes generated IDs. Legacy second-run equivalence is
**not** claimed.

Archive: the source filter is `EVENT_TS < CURRENT_DATE - $$ARCHIVE_DAYS`, using
the session override of 2555 days, not the workflow default of 730. The date is
the UTC date, matching the runner's PostgreSQL session (`Etc/UTC`).
`SEQ_AUDIT_ARCHIVE` starts at 1, in EVENT_ID order. The session stays
**disabled** in `wf_SFX_AUDIT_DAILY` (`ISENABLED="NO"`), and the XML, params and
oracle are unchanged. On replay, dbt appends only the occurrences of a complete
key tuple that are not archived yet, so a rerun adds nothing (**intended
difference**: a legacy rerun re-archives everything with new IDs).

The frozen archive oracle is empty, so `fixture-runner` builds two isolated,
test-only cases in throwaway local PostgreSQL databases and runs the real
`startsession` twice. The 13 source events cover:
- one second before the cutoff, exactly at it and one second after;
- a NULL timestamp;
- all-NULL columns;
- whitespace, a 160-character value, and empty-string versus NULL DETAILS;
- an event older than 730 days but newer than 2555;
- the oldest event with the latest EVENT_ID.

`empty` starts from an empty target and sequence 1. `history` starts with three
prior rows (IDs 7-9) and a persisted sequence of 10. `fixture-load` copies the
identical source and initial target into `PC_AUDIT_UNT4_FIXTURE`, which is the
only schema the guarded writes may touch, and verifies the copy against
PostgreSQL by full multiset comparison. The fixture models are enabled only with
`SFX_UNT4_ARCHIVE_FIXTURE=1` and share the production macro
`pc_audit_event_archive`. A fixture run aborts if the Snowflake UTC date differs
from the runner's CURRENT_DATE.

```sh
cd warehouse  # bind secret:org:SNOWFLAKE_* references at exec time only
TD_PORT=<local pg> .venv/bin/python -m parity.evidence_unt4 fixture-runner --scenario empty
TD_PORT=<local pg> .venv/bin/python -m parity.evidence_unt4 fixture-runner --scenario history
.venv/bin/python -m parity.evidence_unt4 fixture-load
.venv/bin/python -m parity.evidence_unt4 preflight
for s in empty history m_SFX_AUDIT_DAILY_SUMMARY m_SFX_AUDIT_EVENT_ARCHIVE; do
  .venv/bin/python -m parity.evidence_unt4 run --subject $s --run 1
  .venv/bin/python -m parity.evidence_unt4 run --subject $s --run 2
  .venv/bin/python -m parity.evidence_unt4 replay --subject $s; done
.venv/bin/python -m parity.evidence_unt4 postflight
```

Each replay compares typed full-row multisets (oracle vs run 1, oracle vs run 2,
and run 1 vs run 2) and business-key multiplicities. It also checks that
sequence IDs are stable, that runner sessions report SUCCEEDED, FAILED_ROWS=0
and no `.bad` rows, and that no query wrote the target between the two runs
(QUERY_HISTORY_BY_USER window). Neither dbt model has a reject path.

Not certified:
- archive key-tuple collisions (the shared gate fails them by contract);
- source orders that differ from EVENT_ID order;
- archives that are also written by other jobs, where MAX(ID)+1 differs from the
  persisted sequence;
- summary NULL EVENT_TS groups;
- Task DAG execution, control marking (UNT-10) and CI.

## Reproduce local baseline

From repository root:

```sh
make warehouse/.venv/.sfx-installed
make sfx-informatica-up NS=sfx-d1110-before
cd warehouse
.venv/bin/python -m pytest parity/tests -q
.venv/bin/python -m parity.evidence manifest
.venv/bin/python -m parity.evidence oracle
```

The namespace-scoped compose target starts only local PostgreSQL and installs the
runner environment. Each capture creates and drops its own UUID database; logs
and state survive under `parity/out/evidence/unt2_oracle_*`. No shared PC_SRC or
PC_BEFORE uploads occur. Audit runs through `startworkflow`; the three owned
content sessions run through `startsession`, not `wf_SFX_CONTENT_DAILY`, because
that canonical workflow would execute five unowned mappings. Archive runs
standalone without enabling its canonical workflow task.

`manifest.json` freezes landing hashes/counts, resolved session parameters,
bootstrap hash, initial target/source tables and sequence defaults/storage.
Oracle verifies that manifest before each execution. Retain that file unchanged.
Per mapping, `oracle1/` and `oracle2/` contain target typed JSON and typed-cell CSV,
raw reject lines as JSON and CSV, and session results. Reject lines preserve the
runner's own lossy null/empty encoding rather than inventing values. The original
`.bad` files and session/workflow logs remain in each run directory.
`oracle_determinism.json` includes complete multiset differences and reject counts.

## Successor mapping replay protocol

Coordinate exclusive access to the exact owned target. Confirm unchanged source
hashes/parameters against the manifest and record initial target/sequence state.
Execute the scoped dbt node once, capture **all** target rows and rejects, then
execute that same node again without truncation, full-refresh, restore or source
changes. Capture all rows/rejects again and retain execution logs/query IDs.
These execution requirements cannot be proven by snapshot comparison alone.

Serialize each target snapshot as `{columns, types, rows}` using `snapshot()`'s
typed-cell layout. Preserve nulls, string whitespace, numeric precision/scale and
timestamp timezone/precision. Cross-engine type translation must be explicitly
reviewed and representation-only; this strict baseline grants no implicit
numeric-scale or timezone exclusions. Compare rejects separately with the same
complete multiset comparator after lossless typed export.

```sh
.venv/bin/python -m parity.evidence compare --mapping m_SFX_LOGIN_EVENT \
  --oracle parity/out/evidence/m_SFX_LOGIN_EVENT/oracle1/target.json --run1 /path/run1.json
.venv/bin/python -m parity.evidence replay --mapping m_SFX_LOGIN_EVENT \
  --oracle parity/out/evidence/m_SFX_LOGIN_EVENT/oracle1/target.json \
  --run1 /path/run1.json --run2 /path/run2.json
```

Outputs go under `out/evidence/<mapping>/compare.json` or `replay.json`; failures
exit nonzero. Replay requires both runs to equal oracle and each other, zero
duplicate business keys and stable generated IDs per key. Summary keys use the
actual aggregator grouping ports. Archive uses the retained event tuple because
the target lacks source EVENT_ID; tuple collisions deliberately fail the gate.
An empty archive baseline does not prove nonempty sequence allocation parity.

## Content workflow equivalence and live upload smoke

```sh
.venv/bin/python -m parity.evidence content-check
# Bind existing Snowflake secret references at execution time, never via files.
.venv/bin/python -m parity.evidence live-preflight
.venv/bin/python -m parity.evidence live
```

`content-check` runs the canonical full content workflow plus standalone
TEAM_MEMBER in a fresh throwaway local database and compares only the three
owned target multisets against the frozen standalone-session oracle. Nothing
from that extra workflow is uploaded. `content_workflow_equivalence.json` retains
results and local log paths. Routing notes in the manifest and per-asset files
explain eight filtered TIMEOUT logins and three rejected INFO security alerts.

Live preflight asserts 20 distinct control keys with exactly 8/12 owners, then
reads the five relevant PC_SRC landing tables and compares every row against
frozen inputs using shared-loader STG types. Internal audit dependencies remain
the frozen oracle tables, not additional landing inputs. PC_SRC timestamps use
bootstrap precision (0); baseline upload follows `commands.before` TIMESTAMP(9).
DESCRIBE verifies warehouse types before mapping exact representations into the
local snapshot metadata. Integer NUMBER(38,0) and typed PostgreSQL integers share
an exact integer representation; strings, decimal scales and timezone are not
trimmed or discarded. All query SQL, QIDs and results are retained under
`out/evidence/live`, with `transcript.txt` for human review.

`live` lists existing PC_BEFORE tables, replaces only eight owned targets,
uploads nonempty reject outputs into owned `__REJECTS` tables and checks full
readback fidelity. It uses only PC_BEFORE.CAPTURE_STAGE and the owned baselines.
It creates PC_EVIDENCE_SMOKE (fails if already present), tests identical copies
and separate duplicate/value/ID mutations, and drops its scratch schema in a
finally block. This is **HARNESS SMOKE — not mapping parity**; SECURITY_ALERT's
ID mutation tests identity stability, not a claim that ALERT_ID is generated.
Pre/post control snapshots must remain byte-identical, including on failures.

No metrics or success marking is performed. UNT-10 owns acceptance/marking with
owner `migrations-page`. Live mapping parity, DAG execution, CI/SonarQube and
final branch delivery are not certified by this harness smoke.
