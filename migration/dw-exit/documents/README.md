# Documents Step 2a — sfx1119 local proof

**32 green / 10 red objects**, out of 46 non-Spark documents objects minus four retire candidates = **42 in scope**. Local DuckDB only, namespace `sfx-1119-before`, business date `20261109`. No Snowflake connection, object creation, Spark conversion/execution, board changes, or billing behavior edits.

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

Do **not** overwrite the pre-PC snapshot by capturing after those mappings. To create a fresh frozen snapshot on a fresh run, use `parity.object_board.source_snapshot` immediately after the Teradata daily chain and before the PC run: include all documents contract relations except derived M_STORAGE_TOTALS_OUTPUT, SFX_USERS.APP_USER / ROLE_GRANT, and SFX_BILLING.USAGE_DAILY / INVOICE_LINE / SUBSCRIPTION / INVOICE_HDR; then DuckDB EXPORT DATABASE to a new persistent run directory. The report output is materialized by the proof from the actual source macro body.

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
