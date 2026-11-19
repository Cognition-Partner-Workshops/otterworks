# Documents — sfx1119 local proof (Steps 2a–3)

**Step 2a: 32 green / 10 red objects**, out of 46 non-Spark documents objects minus four retire candidates = **42 in scope**. Local DuckDB only, namespace `sfx-1119-before`, business date `20261109`. No Snowflake connection, object creation, board changes, or billing behavior edits. Step 2b Spark results follow below; its separate Spark fixture has 200 rows per input table.

**Not deploy/cutover approval.** The SQL includes diagnostic candidates for unresolved objects. In particular, storage's plain insert preserves duplicates and is intentionally red, not an approved keep-all decision. Do not deploy the chain until owners answer `decisions.json`.

## Artifacts and boundaries

- `00_tables.sql`: eighteen core/staging relations. Run-database placeholders are rendered by the existing run configuration.
- `05_tpt.sql`: nine TPT controls at manifest target `RAW_DOCUMENTS.LOAD_DOCUMENTS`. Requires a separately provisioned `RAW_DOCUMENTS.DOCUMENTS_LANDING` stage with the same `documents/<relation>/<day>.psv` layout. Render `${BUSINESS_DATE}` for this run before deployment, as for billing. Replace/load with a per-file DELETE/COPY transaction (avoiding Snowflake TRUNCATE's implicit commit), forced reread, explicit numeric/date casts, preservation of empty VARCHAR versus NULL numeric/date, abort on bad input.
- `10_load.sql`: executable chain body in source order 01 → 02 → 03 → 04 → 05. `11_procedures.sql` wraps identical bodies at each manifest OPS target (numeric-leading names are quoted). An equality regression prevents drift.
- `20_views.sql`: core and manifest COMPAT views. `35_reports.sql`: callable `OPS.SFX_DOCUMENTS_M_STORAGE_TOTALS` resultset, preserving the half-open date range.
- `../billing/15_storage.sql` is reused unchanged for 10_storage_monthly, **not copied into a second pipeline**. Its BILLING.STORAGE_USAGE_INPUT is bound to documents storage at the boundary. The source daily chain later modifies invoice lines again; comparing that final snapshot to the storage-only output would use the wrong oracle. The proof replays the original BTEQ script inside an explicit PostgreSQL transaction, reads its boundary outputs, and always rolls back. Identical source storage makes both shared outputs green; diagnostic duplicate-preserving storage makes them red.
- `objects.json` maps all 42 manifest object names/targets/types to shipped producer paths. New `warehouse/dbt/models/documents/*` model names match the manifest and expose the converted relations. Mapping/session-facing aliases reuse `warehouse/dbt/models/pc/content/pc_content__{stg_document,document,doc_share}.sql`; those existing business models are unchanged.
- The two `warehouse/snowpark/m_sfx_*.py` mapping publishers expose `run(session)` and MERGE the **existing dbt-produced PC_CONTENT result** into DOCUMENTS. Build the existing PC models in order STG_DOCUMENT → DOCUMENT, and DOC_SHARE, before invoking these publishers. Snowpark registration/runtime, dbt compilation/materialization, and Snowflake collation compatibility were **not** exercised. Local proof renders the actual existing dbt SELECTs and emulates their table/merge materializations; publisher tests check emitted SQL shape only.
- `../parity/documents.json`: twenty-one documents relations including the macro resultset, plus the two shared billing relations; all have explicit keys.
- `../parity/local_documents.py`: reuses `local_billing.statements` for SQLGlot lowering; transactional executor copies BEFORE staging before executing shipped SQL. Independent TPT proof reads the same PSV and executes projections extracted from shipped COPY SQL. Comparisons use `ladder.local_compare` / source-DDL `semantics.char_columns`: row counts, every column's null/min/max/distinct profiles, keyed multiset full-row SHA-256, and samples for **every mismatched key** (sample bound 10000 exceeds this fixture).
- `evidence.json`: persistent complete measurements, landing/session-log SHA-256s, object statuses, and decisions. `.runs/documents-pre-pc` and `.runs/documents-local.json` remain ignored local runtime artifacts.

## Actual source execution and reproducibility

The correct Teradata stack was started with 200 seed rows per table; source daily chain completed successfully. The accidental `sfx1119-before` stack was stopped and its container/network/volume removed using `make sfx-teradata-down NS=sfx1119-before`. Only the correct `sfx-1119-before` PostgreSQL container remains (port 54722).

The oracle is a frozen **post-BTEQ, pre-PowerCenter** snapshot, followed by actual runner outputs from:
```sh
make sfx-informatica-up NS=sfx-1119-before INFA_DB=teradata
make sfx-informatica-run NS=sfx-1119-before INFA_DB=teradata MAPPINGS=m_SFX_STG_DOCUMENT,m_SFX_DOCUMENT,m_SFX_DOC_SHARE
```
Session logs under `etl/informatica/infa_shared/sfx-1119-before/SessLogs` show:
- s_m_SFX_STG_DOCUMENT: read 90, written 90, rejected 0.
- s_m_SFX_DOCUMENT: read 90, written/updated 90, rejected 0.
- s_m_SFX_DOC_SHARE: read 100, written/updated 100, rejected 0.

Do **not** overwrite the pre-PC snapshot by capturing after those mappings. To create a fresh frozen snapshot on a fresh run, use `parity.object_board.source_snapshot` immediately after the Teradata daily chain and before the PC run: take only the 23 Step 2a contract entries whose before schema is TD_DOCUMENTS_BASELINE (not the added Spark entries), excluding derived M_STORAGE_TOTALS_OUTPUT; also include SFX_USERS.APP_USER / ROLE_GRANT, and SFX_BILLING.USAGE_DAILY / INVOICE_LINE / SUBSCRIPTION / INVOICE_HDR. Then DuckDB EXPORT DATABASE to a new persistent run directory. The report output is materialized by the proof from the actual source macro body.

Run the existing frozen proof:
```sh
RUN_TOKEN=sfx1119 warehouse/.venv/bin/python migration/dw-exit/documents/prove_local.py \
  --pre-pc migration/dw-exit/.runs/documents-pre-pc \
  --output migration/dw-exit/.runs/documents-local.json
warehouse/.venv/bin/python -m pytest -q migration/dw-exit/tests
```
The driver intentionally returns complete red measurements rather than treating known differences as success. The JSON object/relation statuses, not process exit alone, are the gate.

Suite result (including unchanged billing coverage):
```text
........................................................................ [ 47%]
...........................ssssssssssssssssssss......................ss. [ 95%]
s......                                                                  [100%]
128 passed, 23 skipped in 11.38s
```

## Differences, attempted disproofs, and decisions

**Integration update:** the owner approved highest-privilege share roles
(ADMIN > EDITOR > other) and highest VERSION_NO on equal latest VERSION_TS.
Converted SQL/dbt and local regression proofs implement both. These deliberately
differ from legacy first-match/arbitrary behavior. The original measurements and
unresolved notes below are historical; `decisions.json` records current approvals.
Raw legacy comparisons are not rewritten to green by these approvals.

1. **SET storage deduplication — unresolved.** Source DDL declares CREATE SET TABLE; the PostgreSQL Teradata runner implements whole-row UNIQUE NULLS NOT DISTINCT with ON CONFLICT DO NOTHING. Same frozen staging: 300 rows, 250 distinct; source core: 250; plain target: 300. To disprove an ingestion/count artifact, independent TPT projection replay matches all 300 staging rows with zero hash delta. Every one of the 50 core hash differences is one extra exact duplicate, not a changed payload. SET behavior is encoded in DDL and `warehouse/teradata/tests/test_estate.py` (explicit minus-50 assertions), but no documents owner-approved billing dedupe policy was found. Existing `set_table_semantics.sql` explicitly requires distinct/keep_all; no approval was inferred from engine behavior. **Question:** discard exact duplicates or retain for charging?
   - Macro: same 70 customers but 50 doubled customer totals → hash delta 100.
   - Shared USAGE_DAILY: 270/270 but 50 changed storage rows → delta 100.
   - Shared INVOICE_LINE: 564/564 but 30 changed charges after existing two-decimal rounding → delta 60. This is upstream extra bytes crossing cent thresholds, **not a new rounding choice**. Identical source storage at the original script boundary produces delta 0 for both shared billing relations.
2. **Latest-version ties — unresolved.** `02_current_versions.bteq` and shipped SQL both order only VERSION_TS DESC. Fifty documents have multiple rows tied at their latest timestamp. On this run, two documents (9000000003 and 9000000019) choose different VERSION_IDs across engines; each competing pair has the same latest timestamp, adjacent version numbers, and one byte difference. Staging replay has delta 0, ruling out changed input. No tie-breaker was added. DOC_VERSION delta 4 propagates to V_DOCUMENT_VERSIONS delta 4 and V_WORKSPACE_STORAGE delta 4. **Question:** which version wins an equal latest timestamp?
   - An initial V_WORKSPACE_STORAGE delta 140 was partly an emulator type artifact: PostgreSQL SUM(bigint) snapshots as Decimal, DuckDB SUM(bigint) as Python int. Values were identical for unaffected owners. Explicit NUMBER(38,0) on target TOTAL_BYTES matches Snowflake/source aggregate numeric representation without rounding; final delta 4 isolates the two real one-byte differences. Source observed SUM scale is 0 and fits precision 38; no unconstrained scale was guessed.
3. **DOC_SHARE multi-role lookup — unresolved generality, seeded parity green.** XML LKP_ROLE_GRANT explicitly uses Use First Value; its connector feeds EXP_ACCESS_LEVEL. `etl/informatica/runner/engine.py` dispatches this connected lookup, caches matches, and returns cands[0] for that policy. Existing dbt joins all matching grants. To disprove a seeded fan-out, frozen ROLE_GRANT has 20 rows / 20 distinct USER_IDs, and actual runner-vs-model output is 100/100, delta 0. A synthetic multi-role regression yields two candidate rows for one SHARE_ID; the local merge guard rejects ambiguity and leaves the target unchanged. The actual runner was **not rerun on a mutated multi-role fixture**; first-match behavior there is established by reachable XML/runner code, not a production observation. Model behavior was not changed. Mapping and session remain red despite green seeded measurements. **Question:** preserve first cached match or approve role precedence?

Owner filtering is **explicit mapping behavior**, not silently invented: m_SFX_DOCUMENT XML calls APP_USER lookup and FIL_KNOWN_OWNER has NOT ISNULL(o_OWNER_STATUS); update strategy chooses DD_INSERT / DD_UPDATE by existing document lookup. Existing dbt mirrors it. Actual same-data runner/model output is 90/90, delta 0. A missing-owner regression confirms that an existing target row is retained rather than deleted by merge when no new candidate survives.

Effective access is explicit XML/model logic: ADMIN → OWNER, EDITOR + VIEW → EDIT, otherwise input access; case/trim normalization is tested. Actual seeded output matches all 100 rows. Multi-role ambiguity is the separate decision above.

CHAR comparison ignores trailing spaces **only** in source-DDL-declared CHAR outputs, never VARCHAR or case differences. Target CHAR replacements are VARCHAR with en-ci-rtrim collation; load statements RTRIM those specific outputs without folding stored case. DuckDB uses NOCASE only as a limited local DDL surrogate; it does not validate live Snowflake collation. Dates/timestamps use native typed values and explicit YYYYMMDD run-date conversion; no session display defaults. Billing rounding is reused unchanged.

## Retire evidence and verdicts

Recomputed READ object-usage rows directly from checked-in `warehouse/teradata/dbql/objectusage.csv` joined to `qrylog.csv`:
- SEARCH_INDEX_LOG: 0 Teradata READs.
- STG_SEARCH_INDEX_LOG: **1** READ, QueryID **111000000072**, user **svc_report_recon**, client **finance-recon-01**, app **BTEQ**, error **0**. Query: `SELECT COUNT(*) AS ROW_COUNT FROM SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG;`. Start **2026-08-12 06:09:33**; inventory last_read **06:09:53** is first response time, not start time.
- V_SEARCH_HISTORY: 0 Teradata READs.
- documents_search_index_log: TPT utility writes STG_SEARCH_INDEX_LOG; query logs measure relation usage, not independent runnable-job retirement.

The manifest/inventory relation-read evidence still agrees. `query_history.sql` and `query_history_assess.sql` query **Snowflake INFORMATION_SCHEMA.QUERY_HISTORY** with run/activity tag filters (24-hour/one-day windows); they do not prove legacy DBQL inactivity or Spark landing inactivity and were not run.

**None of the four retire candidates is approved for deletion in this step.** The view still references core SEARCH_INDEX_LOG. `etl/spark/jobs/py/docs_search_log_parse.py` directly reads SEARCH_INDEX_LOG **landing**, via the common landing helper/schema, and remains in scope for the future Spark step. Source declarations also remain in dbt staging sources. A landing reader is not a Teradata table READ, so zero DBQL reads cannot disprove that dependency. STG has an identified reconciliation caller; confirm its replacement with finance. Retiring the TPT/core/view may be possible separately from preserving landing, but requires an explicit dependency/owner decision. No retire artifacts were converted or deleted.

## Per-object local status

| Object | Manifest target/type | Status | Relations: BEFORE → AFTER; multiset hash delta | Blockers |
|---|---|---|---|---|
| `m_SFX_DOCUMENT` | `TRANSFORM.M_SFX_DOCUMENT` / snowpark | green | DOCUMENT: 90 → 90; Δ0 |  |
| `m_SFX_DOC_SHARE` | `TRANSFORM.M_SFX_DOC_SHARE` / snowpark | red | DOC_SHARE: 100 → 100; Δ0 | m_SFX_DOC_SHARE / s_m_SFX_DOC_SHARE duplicate role lookup |
| `m_SFX_STG_DOCUMENT` | `stg_documents__m_sfx_stg_document` / dbt_model | green | STG_DOCUMENT: 90 → 90; Δ0 |  |
| `s_m_SFX_DOCUMENT` | `core_documents__s_m_sfx_document` / dbt_model | green | DOCUMENT: 90 → 90; Δ0 |  |
| `s_m_SFX_DOC_SHARE` | `core_documents__s_m_sfx_doc_share` / dbt_model | red | DOC_SHARE: 100 → 100; Δ0 | m_SFX_DOC_SHARE / s_m_SFX_DOC_SHARE duplicate role lookup |
| `s_m_SFX_STG_DOCUMENT` | `stg_documents__s_m_sfx_stg_document` / dbt_model | green | STG_DOCUMENT: 90 → 90; Δ0 |  |
| `01_load_folders` | `OPS.01_LOAD_FOLDERS` / snowflake_scripting | green | DOCUMENT: 90 → 90; Δ0; FOLDER: 20 → 20; Δ0 |  |
| `02_current_versions` | `OPS.02_CURRENT_VERSIONS` / snowflake_scripting | red | DOC_VERSION: 90 → 90; Δ4 | SFX_DOCUMENTS.DOC_VERSION |
| `03_load_access` | `OPS.03_LOAD_ACCESS` / snowflake_scripting | green | DOC_SHARE: 100 → 100; Δ0; DOC_TAG: 100 → 100; Δ0 |  |
| `04_load_objects` | `OPS.04_LOAD_OBJECTS` / snowflake_scripting | green | DOC_COMMENT: 200 → 200; Δ0; FILE_OBJECT: 200 → 200; Δ0 |  |
| `05_load_sessions` | `OPS.05_LOAD_SESSIONS` / snowflake_scripting | red | COLLAB_SESSION: 200 → 200; Δ0; STORAGE_USAGE_DAILY: 250 → 300; Δ50 | SFX_DOCUMENTS.STORAGE_USAGE_DAILY |
| `10_storage_monthly` | `OPS.10_STORAGE_MONTHLY` / snowflake_scripting | red | USAGE_DAILY: 270 → 270; Δ100; INVOICE_LINE: 564 → 564; Δ60 | SFX_BILLING.INVOICE_LINE; SFX_BILLING.USAGE_DAILY; Shared billing/15_storage.sql; upstream SET decision pending; see boundary proof |
| `SFX_DOCUMENTS.M_STORAGE_TOTALS` | `OPS.SFX_DOCUMENTS_M_STORAGE_TOTALS` / snowflake_scripting | red | M_STORAGE_TOTALS_OUTPUT: 70 → 70; Δ100 | SFX_DOCUMENTS.M_STORAGE_TOTALS_OUTPUT |
| `SFX_DOCUMENTS.COLLAB_SESSION` | `core_documents__collab_session` / dbt_model | green | COLLAB_SESSION: 200 → 200; Δ0 |  |
| `SFX_DOCUMENTS.DOCUMENT` | `core_documents__document` / dbt_model | green | DOCUMENT: 90 → 90; Δ0 |  |
| `SFX_DOCUMENTS.DOC_COMMENT` | `core_documents__doc_comment` / dbt_model | green | DOC_COMMENT: 200 → 200; Δ0 |  |
| `SFX_DOCUMENTS.DOC_SHARE` | `core_documents__doc_share` / dbt_model | green | DOC_SHARE: 100 → 100; Δ0 |  |
| `SFX_DOCUMENTS.DOC_TAG` | `core_documents__doc_tag` / dbt_model | green | DOC_TAG: 100 → 100; Δ0 |  |
| `SFX_DOCUMENTS.DOC_VERSION` | `core_documents__doc_version` / dbt_model | red | DOC_VERSION: 90 → 90; Δ4 | SFX_DOCUMENTS.DOC_VERSION |
| `SFX_DOCUMENTS.FILE_OBJECT` | `core_documents__file_object` / dbt_model | green | FILE_OBJECT: 200 → 200; Δ0 |  |
| `SFX_DOCUMENTS.FOLDER` | `core_documents__folder` / dbt_model | green | FOLDER: 20 → 20; Δ0 |  |
| `SFX_DOCUMENTS.STG_COLLAB_SESSION` | `stg_documents__collab_session` / dbt_model | green | STG_COLLAB_SESSION: 200 → 200; Δ0 |  |
| `SFX_DOCUMENTS.STG_DOCUMENT` | `stg_documents__document` / dbt_model | green | STG_DOCUMENT: 90 → 90; Δ0 |  |
| `SFX_DOCUMENTS.STG_DOC_COMMENT` | `stg_documents__doc_comment` / dbt_model | green | STG_DOC_COMMENT: 200 → 200; Δ0 |  |
| `SFX_DOCUMENTS.STG_DOC_SHARE` | `stg_documents__doc_share` / dbt_model | green | STG_DOC_SHARE: 100 → 100; Δ0 |  |
| `SFX_DOCUMENTS.STG_DOC_TAG` | `stg_documents__doc_tag` / dbt_model | green | STG_DOC_TAG: 100 → 100; Δ0 |  |
| `SFX_DOCUMENTS.STG_DOC_VERSION` | `stg_documents__doc_version` / dbt_model | green | STG_DOC_VERSION: 300 → 300; Δ0 |  |
| `SFX_DOCUMENTS.STG_FILE_OBJECT` | `stg_documents__file_object` / dbt_model | green | STG_FILE_OBJECT: 200 → 200; Δ0 |  |
| `SFX_DOCUMENTS.STG_FOLDER` | `stg_documents__folder` / dbt_model | green | STG_FOLDER: 20 → 20; Δ0 |  |
| `SFX_DOCUMENTS.STG_STORAGE_USAGE_DAILY` | `stg_documents__storage_usage_daily` / dbt_model | green | STG_STORAGE_USAGE_DAILY: 300 → 300; Δ0 |  |
| `SFX_DOCUMENTS.STORAGE_USAGE_DAILY` | `core_documents__storage_usage_daily` / dbt_model | red | STORAGE_USAGE_DAILY: 250 → 300; Δ50 | SFX_DOCUMENTS.STORAGE_USAGE_DAILY |
| `documents_collab_session` | `RAW_DOCUMENTS.LOAD_DOCUMENTS` / snowflake_scripting | green | STG_COLLAB_SESSION: 200 → 200; Δ0 |  |
| `documents_doc_comment` | `RAW_DOCUMENTS.LOAD_DOCUMENTS` / snowflake_scripting | green | STG_DOC_COMMENT: 200 → 200; Δ0 |  |
| `documents_doc_share` | `RAW_DOCUMENTS.LOAD_DOCUMENTS` / snowflake_scripting | green | STG_DOC_SHARE: 100 → 100; Δ0 |  |
| `documents_doc_tag` | `RAW_DOCUMENTS.LOAD_DOCUMENTS` / snowflake_scripting | green | STG_DOC_TAG: 100 → 100; Δ0 |  |
| `documents_doc_version` | `RAW_DOCUMENTS.LOAD_DOCUMENTS` / snowflake_scripting | green | STG_DOC_VERSION: 300 → 300; Δ0 |  |
| `documents_document` | `RAW_DOCUMENTS.LOAD_DOCUMENTS` / snowflake_scripting | green | STG_DOCUMENT: 90 → 90; Δ0 |  |
| `documents_file_object` | `RAW_DOCUMENTS.LOAD_DOCUMENTS` / snowflake_scripting | green | STG_FILE_OBJECT: 200 → 200; Δ0 |  |
| `documents_folder` | `RAW_DOCUMENTS.LOAD_DOCUMENTS` / snowflake_scripting | green | STG_FOLDER: 20 → 20; Δ0 |  |
| `documents_storage_usage_daily` | `RAW_DOCUMENTS.LOAD_DOCUMENTS` / snowflake_scripting | green | STG_STORAGE_USAGE_DAILY: 300 → 300; Δ0 |  |
| `SFX_DOCUMENTS.V_DOCUMENT_VERSIONS` | `COMPAT.SFX_DOCUMENTS__V_DOCUMENT_VERSIONS` / compatibility_view | red | V_DOCUMENT_VERSIONS: 90 → 90; Δ4 | SFX_DOCUMENTS.V_DOCUMENT_VERSIONS |
| `SFX_DOCUMENTS.V_WORKSPACE_STORAGE` | `COMPAT.SFX_DOCUMENTS__V_WORKSPACE_STORAGE` / compatibility_view | red | V_WORKSPACE_STORAGE: 70 → 70; Δ4 | SFX_DOCUMENTS.V_WORKSPACE_STORAGE |

## Per-relation local measurements

Red decisions override a matching measurement. All profiles, full checksums and every mismatched key sample are in `evidence.json`. A changed row contributes two to the multiset hash delta; an added duplicate contributes one.

| Boundary | Relation | BEFORE | AFTER | Hash delta | Measured |
|---|---|---:|---:|---:|---|
| sql_relations | COLLAB_SESSION | 200 | 200 | 0 | green |
| sql_relations | DOCUMENT | 90 | 90 | 0 | green |
| sql_relations | DOC_COMMENT | 200 | 200 | 0 | green |
| sql_relations | DOC_SHARE | 100 | 100 | 0 | green |
| sql_relations | DOC_TAG | 100 | 100 | 0 | green |
| sql_relations | DOC_VERSION | 90 | 90 | 4 | red |
| sql_relations | FILE_OBJECT | 200 | 200 | 0 | green |
| sql_relations | FOLDER | 20 | 20 | 0 | green |
| sql_relations | STG_COLLAB_SESSION | 200 | 200 | 0 | green |
| sql_relations | STG_DOCUMENT | 90 | 90 | 0 | green |
| sql_relations | STG_DOC_COMMENT | 200 | 200 | 0 | green |
| sql_relations | STG_DOC_SHARE | 100 | 100 | 0 | green |
| sql_relations | STG_DOC_TAG | 100 | 100 | 0 | green |
| sql_relations | STG_DOC_VERSION | 300 | 300 | 0 | green |
| sql_relations | STG_FILE_OBJECT | 200 | 200 | 0 | green |
| sql_relations | STG_FOLDER | 20 | 20 | 0 | green |
| sql_relations | STG_STORAGE_USAGE_DAILY | 300 | 300 | 0 | green |
| sql_relations | STORAGE_USAGE_DAILY | 250 | 300 | 50 | red |
| sql_relations | V_DOCUMENT_VERSIONS | 90 | 90 | 4 | red |
| sql_relations | V_WORKSPACE_STORAGE | 70 | 70 | 4 | red |
| sql_relations | M_STORAGE_TOTALS_OUTPUT | 70 | 70 | 100 | red |
| tpt_relations | STG_COLLAB_SESSION | 200 | 200 | 0 | green |
| tpt_relations | STG_DOCUMENT | 90 | 90 | 0 | green |
| tpt_relations | STG_DOC_COMMENT | 200 | 200 | 0 | green |
| tpt_relations | STG_DOC_SHARE | 100 | 100 | 0 | green |
| tpt_relations | STG_DOC_TAG | 100 | 100 | 0 | green |
| tpt_relations | STG_DOC_VERSION | 300 | 300 | 0 | green |
| tpt_relations | STG_FILE_OBJECT | 200 | 200 | 0 | green |
| tpt_relations | STG_FOLDER | 20 | 20 | 0 | green |
| tpt_relations | STG_STORAGE_USAGE_DAILY | 300 | 300 | 0 | green |
| pc_relations | STG_DOCUMENT | 90 | 90 | 0 | green |
| pc_relations | DOCUMENT | 90 | 90 | 0 | green |
| pc_relations | DOC_SHARE | 100 | 100 | 0 | green |
| shared_billing_boundary | USAGE_DAILY | 270 | 270 | 0 | green |
| shared_billing_boundary | INVOICE_LINE | 564 | 564 | 0 | green |
| shared_billing_with_candidate_storage | USAGE_DAILY | 270 | 270 | 100 | red |
| shared_billing_with_candidate_storage | INVOICE_LINE | 564 | 564 | 60 | red |

## Step 2b — documents-assigned Spark jobs

**13 actual legacy jobs succeeded; all 13 lake rowsets match, with zero hash delta and identical column profiles. Spark gate after Step 3: 13 green / 0 red.** The two Step 2b escalations were incorrect: partition write mode and JDBC publication are explicit coded behavior. They are now converted and proven, not owner decisions. Only the original three Step 2a decisions remain, unchanged.

All manifest `target_type` values are `dbt_model`. Models are under `warehouse/dbt/models/spark/<job>/<job>.sql`, with explicit aliases **`MART_SPARK.spark__<job>`**, exactly the manifest target. Python UDF pre-hooks in `warehouse/dbt/macros/documents_spark_udfs.sql` ship the actual legacy function bodies; local execution extracts those shipped bodies, not a second hand-written approximation. Tests compare their ASTs to the legacy functions. Recursive SQL replaces bounded RDD walks; Scala share-activity SQL is preserved, and compaction selects from the shipped hourly model using dbt `ref`.

The approved manifest is **unchanged** and still lacks all 13 `output_relations`. `parity/documents.json` declares 13 keyed lake relations plus the produced JDBC equivalent COMPAT.SPARK_ALERT_ANOMALY. `spark_jobs.json` records each manifest target, source, input relation, owner/provenance, model path, dependency, keys and known data callers. The 23 Step 2a relations remain present. Step 3 integrates the board below; existing billing model/adapter behavior is unchanged. `ladder.local_compare` gained optional contract keys; its existing default first-column hashes and behavior are preserved and regression-tested.

### Per-job evidence and data callers

Counts are actual Parquet → shipped conversion; **every row below has hash delta 0** and no sampled row differences. The key is the comparison key, not an assertion that the legacy source enforces uniqueness. Full multiset hashes preserve duplicate multiplicity. All thirteen manifest owners are **`@otterworks/data-platform`, `owner_source: proposed`**.

| Job | Before → after | Contract keys | Gate | External business-data caller found |
|---|---:|---|---|---|
| collab_session_sessionize | 200 → 200 | USER_ID, DOCUMENT_ID, SESSION_NUMBER | green | none |
| doc_share_graph_reach | 5 → 5 | USER_ID | green | none |
| doc_version_diff_stats | 200 → 200 | DOC_VERSION_ID | green | none |
| docs_event_export_hourly | 200 → 200 | DOCUMENT_ID | green | lake_compaction_documents, `etl/spark/scala/src/main/scala/sfx/LakeCompactionDocuments.scala` |
| docs_folder_legacy_report | 200 → 200 | FOLDER_ID | green | none; legacy cron disabled |
| docs_folder_tree_walk | 200 → 200 | FOLDER_ID | green | none |
| docs_search_log_parse | 200 → 200 | SEARCH_INDEX_LOG_ID | green | none; still reads SEARCH_INDEX_LOG landing, not core |
| docs_share_activity | 150 → 150 | OWNER_USER_ID, PERMISSION | green | none |
| docs_storage_by_owner | 50 → 50 | USER_ID, EMAIL | green | none |
| docs_tag_normalize | 200 → 200 | DOC_TAG_ID | green | none |
| file_object_binary_extract | 200 → 200 current; 400 → 400 history | FILE_OBJECT_ID, RUN_DATE | green | none |
| lake_compaction_documents | 200 → 200 | DOCUMENT_ID | green | none |
| security_alert_anomaly | 200 → 200 lake; 200 → 200 JDBC | ALERT_ID | green | none in repository; also publishes JDBC output |

Caller search covered consumers/registry.yaml, consumers/reports and consumer sources, services, Teradata, PowerCenter, and other Spark jobs. No consumers-registry/report references to these output names were found. Absence in this repository is not proof of no external consumers. All jobs have their own registry, submit script, k8s application and cron.d entry, plus entries in `etl/crontab`; these are execution callers, not downstream rowset consumers. `docs_folder_legacy_report` cron entries are commented out; it was run explicitly for this request, not re-enabled.

No `.github/CODEOWNERS` rule assigns Spark paths to a different owner, and no consumer-registry row supplies a competing output owner. Thus proposed ownership is **not CODEOWNERS-confirmed**. A real cross-owner input is `docs_storage_by_owner`: users.APP_USER maps to users' `SFX_USERS.APP_USER`, whose manifest owner is `@otterworks/analytics` (DBQL readership), unlike the job's proposed data-platform owner. `security_alert_anomaly` is documents-assigned but reads audit.SECURITY_ALERT and writes **lake/audit**, not lake/documents; its JDBC output is audit too. SECURITY_ALERT's manifest owner is also proposed data-platform, so this is a subject-area/shared-table concern rather than a demonstrated conflicting team assignment.

`etl/spark/classification.yaml` is a different, conflicting classification and was not edited: folder report and compaction are classified retired; graph reach, version diff, folder walk, search parse, tag normalization and anomaly are Snowpark; binary extraction is spark_standard_template. The migration manifest decides this step: all 13 received its dbt target, including the two classified retired. Existing registry statuses, launchers, classification, consumers and schedules were left unchanged.

### Explicit behavior converted and causal evidence

1. **Binary packaging fixed without changing extraction.** `common/binary_documents.py` imports warehouse.run_config. Both archive builders (`common/package.py` and fixture `initialize.py`) previously included common modules only. They now add only an empty warehouse/__init__.py and the existing run_config.py. The actual job subsequently produced `BINARY_OUTPUT_ROWS=200 RUN_DATE=2026-11-19`. Isolated `python -I` tests of each builder import the zipped binary helper without the checkout on sys.path, ruling out accidental host-package resolution. No parsing, filters, defaults, grouping or error handling were changed.
2. **Binary partition history — explicit write mode, converted and green.** `main` calls `drop_unpartitioned` and `save_partition`; the latter explicitly uses dynamic partition overwrite with partitionBy(run_date), or static current-partition overwrite when empty. The model is now incremental append with a shipped pre-hook DELETE restricted to the current RUN_DATE; full refresh is disabled. Other dates survive, repeat dates replace rather than duplicate, and an empty current batch clears only that date. The local executor extracts and executes the shipped DELETE, not a separate formula. `replay_spark.py` executed the actual legacy job with SFX_RUN_DATE=2026-11-18 then 2026-11-19 on the identical SHA-256 landing. Starting from the pre-existing 19th partition, source/target progressed **200/200 → 400/400 → 400/400**, with identical profiles and zero keyed hash/sample deltas at every phase. The second run replaces an existing date and retains the first; duplicate-sensitive hashes rule out append duplication. `spark-replay.json` retains commands, complete measurements and input/output/log/code fingerprints. A synthetic empty-batch regression covers the static-empty branch; changed-payload and actual empty-Spark replays were not performed. The explicit model date is bound from the successful log; no business-date default is invented. Live raw BINARY ingestion and Snowflake materialization remain unverified.
3. **Audit JDBC publication — explicit side output, converted and green.** `security_alert_anomaly.main` calls `common.runtime.save(..., 'audit', ..., 'sfx_audit.SPARK_ALERT_ANOMALY')`; save writes Parquet then overwrites JDBC. The shipped `security_alert_anomaly_jdbc.sql` materializes COMPAT.SPARK_ALERT_ANOMALY from the converted base model. The adapter reads actual PostgreSQL rows independently and executes this shipped SELECT in DuckDB: **200/200**, identical profiles, ALERT_ID keyed full-row hash delta 0, no samples. This is not inferred from lake parity. Both audit outputs are in the contract. The manifest assigns SFX_AUDIT.SECURITY_ALERT to **audit**; SFX_AUDIT.SPARK_ALERT_ANOMALY has **no separate manifest object/area assignment**. Both are recorded as shared audit tables produced/read by a documents-assigned Spark job; the approved manifest is unchanged.

There were **no seeded row differences to normalize**. Initial adapter plumbing errors (DuckDB JSON type registration and quoted relation identifiers) were diagnosed and fixed before successful measurements. No rounding tolerance, filter, default, dedupe or altered UDF was introduced to make a comparison pass.

### Conversion rules learned and unproven boundaries

- Spark string outputs are compared exactly, including case, whitespace, binary SHA-256 and Python exception strings; no Teradata CHAR-padding rule is applied to Spark strings. Python regex Unicode behavior, null handling, `difflib.SequenceMatcher`, PDF/DOCX/ZIP decoding and malformed-content handling stay in the shipped Python UDF bodies.
- Session split is **strictly greater than 1800 seconds**, including fractional seconds; a microsecond boundary regression prevents truncation. RDD graph joins can match null keys, unlike ordinary SQL `=`; the recursive model preserves that, seed user 1, visited/minimum distance, cycles and four hops. Folder walking preserves the 20-iteration cap and Python's zero-parent truthiness rather than silently repairing it.
- Hourly export's nonnegative modulo bucket and hive partition column survive logical comparison. Binary run_date is a string in the legacy rowset; DuckDB hive date inference is cast back to VARCHAR before comparing. Physical directory layout, number of files, compaction coalesce(4), sorting/distribution and compression are **not** established by row parity.
- Spark uses a separate landing fixture from Teradata/PowerCenter. Binary partition accumulation and repeated-date replacement are now established by actual two-date replay on unchanged landing, and the JDBC side rowset is separately proven. Changed-payload updates, actual empty-Spark replay, late arrivals, equal VERSION_NUMBER lag winners, conflicting duplicate parent IDs, failure atomicity, large/external blobs and runtime Snowflake UDF/dbt execution remain unverified.
- No Snowflake connection or object creation was attempted. Board regeneration is local evidence only, not Spark cutover or retire approval.

### Reproduction and checks

The actual stack was started with:
```sh
make sfx-spark-up NS=sfx-1119-before ROWS_PER_TABLE=200
```
Then `make sfx-spark-run NS=sfx-1119-before JOB=<job>` was run separately for each of the thirteen jobs above, with hourly export before compaction. Actual logs and Parquet remain under `etl/spark/.data/sfx-1119-before/{logs,lake}`. Do not regenerate landing after these runs and then reuse their outputs.

```sh
RUN_TOKEN=sfx1119 warehouse/.venv/bin/python migration/dw-exit/parity/spark_documents.py \
  --namespace sfx-1119-before --output migration/dw-exit/.runs/documents-spark.json
RUN_TOKEN=sfx1119 warehouse/.venv/bin/python migration/dw-exit/documents/replay_spark.py \
  --dates 2026-11-18 2026-11-19 --output migration/dw-exit/documents/spark-replay.json
make -o sfx-teradata-up sfx-manifest-board RUN_TOKEN=sfx1119 NS=sfx-1119-before BOARD_ROWS=200 PARITY_TARGET=duckdb
warehouse/.venv/bin/python -m pytest -q migration/dw-exit/tests
make sfx-manifest-board-test
make sfx-spark-test
```

The adapter fails closed per object on missing inputs, missing nested Parquet/logs, failed execution logs, output older than any landing input, or compaction older than its upstream lake output. A downstream candidate requires upstream parity first. Current binary comparison is restricted to the successful log's partition; a separate cumulative replay compares the entire two-date lake. The board rejects replay evidence if any landing, Parquet, execution log, source/conversion fingerprint or partition set changes. `evidence.json` contains actual SQL/PC/current Spark/JDBC measurements plus validated cumulative replay; source and target are separate DuckDB connections. JSON status, not process exit alone, is the gate.

Step 2b checks (superseded by Step 3 checks below):
```text
........................................................................ [ 42%]
...........................ssssssssssssssssssss......................ss. [ 85%]
s.......................                                                 [100%]
145 passed, 23 skipped in 11.66s

Ran 54 tests in 35.923s

OK
LOCAL_JOBS billing_revenue_by_plan docs_tag_normalize user_pref_json_flatten: OK (2000 rows)
SCALA_IDS IntegerType, LongType (>2^31), empty inputs and missing columns: OK
python3 etl/spark/history/compute_baseline.py --check
Baseline matches 30 applications.
```

Spark tests emitted optional native-Hadoop/hostname fallback and socket ResourceWarnings; they did not fail. The Java 17/uv/PySpark environment was checked and is loaded. Live Snowflake dbt parsing/materialization, external blob ingestion and Python UDF registration remain unverified.

## Step 3 — generated parity board and final gates

**59 objects: 45 green / 4 retire candidates / 10 red.** The four retire candidates remain SEARCH_INDEX_LOG, STG_SEARCH_INDEX_LOG, documents_search_index_log and V_SEARCH_HISTORY; this category is not deletion approval. The ten executable reds are still explained by the original three reviewed decisions:

- SET storage policy: STORAGE_USAGE_DAILY, 05_load_sessions, M_STORAGE_TOTALS and shared 10_storage_monthly (4 objects).
- Latest VERSION_TS ties: DOC_VERSION, 02_current_versions, V_DOCUMENT_VERSIONS and V_WORKSPACE_STORAGE (4 objects).
- Multiple-role Use First Value lookup: m_SFX_DOC_SHARE and s_m_SFX_DOC_SHARE (2 objects); seeded parity matches, precedence remains unresolved.

`object_board.py` now dispatches documents proof alongside billing. `documents_board.py` reruns the actual shipped SQL/PC/current Spark/JDBC comparisons and validates saved actual binary replay before exporting per-object metrics. The generated `board/board.json` and `board/README.md` contain all 59 documents rows, full profiles/hashes/samples, producer/source ranges, metric code and evidence links. The generated [PR parity table](parity-table.md) summarizes relation-level proof legs; counts can repeat across legs and must not be summed as distinct objects.

`provenance_subjects.json` selects **devin/sfx1119-documents-migration** for documents and retains **devin/sfx1119-billing-parity** for billing. Billing metric ranges are pinned to the SHA-256 of its evidence-branch source, so the longer documents-era ladder implementation cannot move billing's links. Documents metric ranges come from the current ladder AST. Every documents Snowflake leg is independently **red/denied**, with the actual recorded preflight error 002003, capture_run=false and prove_run=false. Local metrics never imply a live Snowflake execution.

Billing's six Spark lake outputs were absent in this workspace, so the unchanged legacy jobs were executed once on the same deterministic 200-row fixture to restore them; the append job had no existing output and was not appended twice. All six completed OK. The regenerated **74 billing rows are byte-for-byte identical** to the pre-Step-3 board rows, including counts, profiles, hashes, samples, status and branch/range links. No billing conversion or adapter was changed.

All new documents conversion rules and the proof/replay/board commands are recorded in `.agents/skills/teradata-to-snowflake/SKILL.md` in cause / symptom / rule / files form. No Snowflake object creation, live UDF registration, cutover or retire action was performed. Empty partition replacement is unit-tested; actual replay covers two dates and replacement of an existing date on identical input, not changed payloads, failure atomicity or external blob ingestion at scale.

Final Step 3 checks:
```text
warehouse/.venv/bin/python -m pytest -q migration/dw-exit/tests
153 passed, 23 skipped in 14.00s

make sfx-manifest-board-test
153 passed, 23 skipped in 12.77s

make sfx-spark-test
Ran 54 tests in 36.405s

OK
LOCAL_JOBS billing_revenue_by_plan docs_tag_normalize user_pref_json_flatten: OK (2000 rows)
SCALA_IDS IntegerType, LongType (>2^31), empty inputs and missing columns: OK
Baseline matches 30 applications.

Billing rows byte-for-byte unchanged: 74/74; SHA-256 ab436fe707fb1b2507e570ed59ce36c3a9d79a282d2092d49d8082af2f3c1333
Documents Snowflake legs: 59/59 recorded red/denied; capture/prove false.
```
