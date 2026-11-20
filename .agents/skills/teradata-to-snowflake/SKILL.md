---
name: teradata-to-snowflake
description: Run warehouse tooling and prove Teradata-to-Snowflake conversions with local and live parity evidence.
---

# Local estate mechanics

Run commands from the repository root. Use an estate checkout containing the Spark baseline
and manifest-board changes; the board targets and legacy Spark sources are supplied there.
Requires Docker Compose, Python 3.11+, uv and Java 21 for Spark tests.

## Run scope

```sh
export RUN_TOKEN=sfx1119
eval "$(python3 warehouse/run_config.py env)"
export NS="$RUN_BEFORE_NAMESPACE"
```

## Teradata emulator and PowerCenter runner

```sh
make sfx-teradata-up NS="$NS" ROWS_PER_TABLE=200
make sfx-teradata-test NS="$NS"
make sfx-informatica-up NS="$NS" INFA_DB=teradata
make sfx-informatica-run NS="$NS" INFA_DB=teradata MAPPINGS=all
make sfx-informatica-test NS="$NS" INFA_DB=teradata
```

Landing files: `warehouse/landing/`. Runner output:
`etl/informatica/infa_shared/<NS>/{SessLogs,WorkflowLogs,TgtFiles,BadFiles}`.
Database port is computed from NS by the Make targets.

## Spark

```sh
make sfx-spark-up NS="$NS"
make sfx-spark-test
make sfx-spark-run NS="$NS"
```

Runtime files are under `etl/spark/.data/<NS>/{landing,lake,eventlogs,logs}`;
history inputs are under `etl/spark/history/`. Inspect the History Server's
`/api/v1/applications` endpoint at the host port shown by `docker ps` for
the namespace's Spark history container.

## dbt and local parity

```sh
make sfx-snowflake-test SFX_PYTHON=python3.11
make sfx-manifest-board NS="$NS" BOARD_ROWS=200 PARITY_TARGET=duckdb
make sfx-manifest-board-test
make sfx-target-sql
make sfx-feed-target-test
```

The dbt test target includes an offline parse. Its project and artifacts are under
`warehouse/dbt/`. Board output: `migration/dw-exit/board/board.json`.
SQL generation prints to stdout and does not open a target connection.
`make sfx-snowflake-dbt` runs a live build and requires separately provisioned target
credentials; it is not needed for local DuckDB checks.

## Conversion rules

- DBQL TablesV includes M/P catalog rows and last-access timestamps / ACCOUNT_USAGE differs / owner approved only M/P catalog omissions and last-access timestamp differences; retained T/V rows and access counts must match / `dbc/decisions.json`, `parity/dbc_retire.py`.
- DBQL records process, client, CPU, IO and collection metadata / QUERY_HISTORY cannot project equivalent values / owner approved missing CPU/IO/client-id/ProcID as NULL and collection/access timestamp differences; compare every retained field and multiplicity through the generic deviation gate; StatementGroup is NOT approved and keeps query-log views red; QUERY_TAG as AppID remains a local assumption / `dbc/decisions.json`, `dbc/README.md`, `parity/owner_decisions.py`, `parity/dbc_retire.py`.
- DBQL ObjectUsage includes writes and executes / ACCESS_HISTORY lacks M/P EXECUTE attribution / owner approved only missing rows satisfying EXECUTE AND M/P; retain READ/WRITE and non-M/P EXECUTE rows, never filter target extras / `dbc/decisions.json`, `dbc/10_account_usage.sql`, `parity/dbc_retire.py`.
- Snowflake FLATTEN over an object array / sqlglot DuckDB UNNEST lowering is invalid / lower only the shipped FLATTEN table function to DuckDB json_each before transpilation / `parity/dbc_retire.py`.
- Snowflake VARIANT scalar ::VARCHAR unquotes strings / DuckDB JSON cast retains quotes and breaks object joins / lower shipped objectName/objectDomain scalar extraction to json_extract_string for local proof / `parity/dbc_retire.py`.
- Partial catalog equivalence / full-shape red hides correct mapped fields / add a separately labelled mapped-column ladder with explicit supported row scope, never promoting full-object status from it / `parity/dbc_retire.py`.

Retire evidence: DBC setup-date COUNT(*) reads are not proof of deletion safety. Compare
current DBQL reads with inventory and pinned BEFORE_STATE, scan services/etl callers,
retain emulator drift separately, and require owner approval. Local ACCOUNT_USAGE
emulation is an assumption; no live Snowflake connection is needed or implied.

- PowerCenter session writer options are part of mapping semantics / append-only event conversion loses updates / translate `Treat source rows as=Update` plus `Update else Insert=YES` to keyed MERGE, independently of target truncation / `audit/50_powercenter.sql`, source `wf_SFX_AUDIT_DAILY.XML`.
- Unsorted PowerCenter aggregate feeding a sequence / equal counts and profiles can hide different surrogate-key assignments / keep keyed hashes red; diagnose first-seen runner ordering separately from aggregate values, never impose or emulate an undocumented input order / `parity/powercenter_audit.py`, `audit/README.md`.

- Teradata CHAR(n) pads stored values / string-only row hash gaps / store target strings unpadded and ignore trailing spaces only for source-DDL-declared CHAR outputs (including view lineage), recording affected columns; all other values exact / `billing/15_storage.sql`, `parity/semantics.py`, `parity/ladder.py`.
- Teradata NOT CASESPECIFIC equality / missing plan joins and split currency groups / use `COLLATE 'en-ci-rtrim'` on corresponding target columns and portable `UPPER(RTRIM())` plan joins; live collation compatibility remains unverified / `billing/00_tables.sql`, `20_routines.sql`, `30_views.sql`.
- Unconstrained NUMERIC aggregate metadata / rounded BEFORE totals / derive decimal scale from actual source values rather than defaulting missing scale to zero; reject unsupported precision instead of silently rounding / `parity/semantics.py`, `parity/object_board.py`, `billing/capture.py`.
- Teradata DATE-to-INTEGER encoding plus 19000000 / incorrect period keys / construct `YEAR(date)*10000+MONTH(date)*100+DAY(date)` rather than elapsed days / `billing/40_close.sql`.
- Teradata explicit date FORMAT / wrong or session-dependent invoice period / use `TO_CHAR(date, 'YYYY-MM')`, never a substring of session-default date display / `billing/30_views.sql`, `40_close.sql`.
- Source GL replacement is month-scoped / missing historical journal rows / delete only `[month_start,next_month_start)` before posting / `billing/20_routines.sql`, from `warehouse/teradata/scripts/billing/12_invoice_monthly.bteq`.
- Source journal IDs include run month and a credit-note offset / journal key/hash gaps / preserve `YYYYMM*1000000000000` and the separate credit reversal offset / `billing/20_routines.sql`.
- Source account load also inserts staging journals / unavailable or missing GL outputs / preserve the staging insert with its posting-date NOT EXISTS guard / `billing/10_load.sql`, from `warehouse/teradata/scripts/billing/01_load_accounts.bteq:20–21`.
- Source daily_chain runs storage, monthly billing and close after loads / incomplete invoice lines, totals, usage and close fields / execute fixed `10→15→20→30→40`, extracting the shipped procedure body rather than copying logic / `parity/local_billing.py`, `parity/object_board.py`.
- Teradata macro/export resultsets are outputs too / five unmeasured report rows / declare resultset relations, execute original macro/export SELECTs after the source chain and shipped procedure RESULTSET bodies on the target; retain the trial-balance TOTAL row and NULL-to-zero sums / `parity/report_outputs.py`, `billing/35_reports.sql`, `tools/assess.py`.
- Teradata ZEROIFNULL sums / PostgreSQL emulator rejects a raw exported SELECT / lower ZEROIFNULL to COALESCE(value, 0) for emulator execution, matching the shipped Snowflake report / `parity/report_outputs.py`, `billing/35_reports.sql`.
- Spark monthly date_format('yyyy-MM') / trial balance splits into daily groups if sqlglot drops TO_CHAR's format / ship explicit Snowflake TO_CHAR(date, 'YYYY-MM') and explicitly map it to DuckDB STRFTIME for local proof / `warehouse/dbt/models/spark/billing_gl_trial_balance/billing_gl_trial_balance.sql`, `parity/spark_billing.py`.
- Spark usage job emits only MAX(USAGE_DATE) even on its first run / target first-build backfill has extra rows / apply the latest-date predicate on initial as well as incremental dbt builds / `warehouse/dbt/models/spark/billing_usage_append_daily/billing_usage_append_daily.sql`.
- Spark Python churn scoring / a separately rewritten formula would not prove the shipped conversion / extract the shipped Snowpark UDF and projection, register that Python body in DuckDB, and compare actual Spark Parquet against the same landing PSVs / `parity/spark_billing.py`, `warehouse/snowpark/billing_churn_score.py`.
- Explicit legacy write modes and side publications / falsely escalating implemented behavior as an owner question / convert coded append, partition replacement, filters, defaults and JDBC writes faithfully; reserve owner decisions for undocumented policy or unspecified winners, not implementation work / `documents/replay_spark.py`, `parity/spark_documents.py`, `warehouse/dbt/models/spark/file_object_binary_extract/file_object_binary_extract.sql`, `warehouse/dbt/models/spark/security_alert_anomaly/security_alert_anomaly_jdbc.sql`.
- Teradata SET storage semantics / 300 staging rows become 250 exact-distinct core rows and change downstream charges / require an explicit SET-table migration policy rather than treating a plain insert as parity; keep the reviewed dedupe owner decision red and show every exact duplicate / `documents/decisions.json`, `documents/00_tables.sql`, `warehouse/dbt/macros/set_table_semantics.sql`, `warehouse/teradata/tests/test_estate.py`.
- ROW_NUMBER ordered only by latest timestamp / different current versions with identical VERSION_TS / retain the incomplete ordering diagnostically, expose all competing winners and propagated view differences, and obtain a tie policy rather than inventing an ID/version tiebreaker / `documents/10_load.sql`, `documents/decisions.json`, `warehouse/teradata/scripts/documents/02_current_versions.bteq`.
- Connected PowerCenter lookup uses Use First Value / a relational join fans out on multiple matching grants although the seeded fixture is unique / follow XML connector and runner dispatch to establish the first cached match; reject ambiguous merge candidates and keep the reviewed precedence decision red until ordering is approved / `warehouse/dbt/models/pc/content/pc_content__doc_share.sql`, `parity/local_documents.py`, `documents/decisions.json`, `etl/informatica/runner/engine.py`.
- Explicit PowerCenter known-owner filter and update strategy / missing owners can wrongly delete existing target rows / preserve APP_USER lookup, NOT ISNULL owner-status filtering and insert/update behavior; test seeded output, missing-owner retention and ambiguous-key rollback against the actual runner / `documents/prove_local.py`, `parity/local_documents.py`, `warehouse/dbt/models/pc/content/pc_content__document.sql`.
- Shared documents storage step writes billing tables before later chain mutations / final invoice snapshot is the wrong oracle for storage-only SQL / reuse billing/15_storage.sql unchanged, replay the original BTEQ boundary in a PostgreSQL transaction, capture both outputs and always roll back; separate identical-input boundary proof from propagation of the unresolved SET policy / `documents/prove_local.py`, `billing/15_storage.sql`, `warehouse/teradata/scripts/documents/10_storage_monthly.bteq`.
- PowerCenter mutates source core tables after the daily chain / post-PC data invalidates the SQL baseline / freeze post-BTEQ/pre-PC source state before mappings and compare mapping results with actual post-PC output separately; never recapture over that checkpoint / `documents/prove_local.py`, `parity/documents_board.py`, `documents/README.md`.
- Documents TPT strings, numbers and date encodings differ / empty strings, NULL numerics, padding or session-formatted dates alter profiles / execute shipped COPY projections independently on the same PSV, preserve empty VARCHAR versus NULL numeric/date, trim only declared CHAR outputs, use explicit scale/date casts and abort bad input / `documents/05_tpt.sql`, `parity/local_documents.py`, `parity/semantics.py`.
- Documents macro returns a half-open date-range resultset / table parity omits a serving output or includes the next boundary / declare and execute both original macro SELECT and shipped RESULTSET body using start-inclusive/end-exclusive dates, including empty/error cases / `documents/35_reports.sql`, `parity/local_documents.py`, `parity/documents.json`.
- Spark Python regex, difflib and binary extraction are not equivalent to convenient SQL functions / Unicode, NULL, similarity, malformed-content or checksum differences / ship extracted legacy Python bodies, execute those same bodies in DuckDB, compare their ASTs to source and preserve Python exception strings without normalization / `warehouse/dbt/macros/documents_spark_udfs.sql`, `parity/spark_documents.py`, `tests/test_spark_documents.py`.
- Spark session gaps are strictly greater than 1800 seconds / integer-second truncation merges events 1800.000001 seconds apart / compare microseconds against 1800000000 and preserve exactly-1800-second adjacency / `warehouse/dbt/models/spark/collab_session_sessionize/collab_session_sessionize.sql`, `tests/test_spark_documents.py`.
- RDD graph joins can match NULL keys and subtract visited nodes / ordinary SQL equality loses reachable users or repeated cycles change distance / use null-safe joins, seed user 1, bound expansion to four hops and retain minimum distance; test cycles, NULL edges and the hop cap / `warehouse/dbt/models/spark/doc_share_graph_reach/doc_share_graph_reach.sql`, `tests/test_spark_documents.py`.
- Folder walk uses parent-or-current Python truthiness and a 20-step cap / treating parent 0 as an ordinary edge silently repairs source behavior / preserve zero-parent truthiness and the exact iteration/depth rules; do not claim duplicate broadcast-key ordering from a unique-key fixture / `warehouse/dbt/models/spark/docs_folder_tree_walk/docs_folder_tree_walk.sql`, `tests/test_spark_documents.py`.
- Spark pmod and partition columns / negative document IDs bucket differently or hive inference changes a string run_date to DATE / retain nonnegative modulo and reconstitute hive partition columns with source types before hashing; logical row parity does not prove physical directory/file counts or coalesce behavior / `warehouse/dbt/models/spark/docs_event_export_hourly/docs_event_export_hourly.sql`, `parity/spark_documents.py`.
- Binary save_partition explicitly overwrites one date and retains other partitions / table rebuild loses history or append duplicates reruns / use incremental append with a shipped current-date DELETE pre-hook, disable full refresh, require an explicit run_date, clear an empty current partition too, and prove two actual legacy dates plus rerun replacement against the same landing / `warehouse/dbt/models/spark/file_object_binary_extract/file_object_binary_extract.sql`, `warehouse/dbt/macros/documents_spark_udfs.sql`, `documents/replay_spark.py`, `documents/spark-replay.json`.
- Binary helper imports warehouse.run_config on executors / No module named warehouse despite successful host imports / include warehouse/__init__.py and the existing run_config.py in BOTH initializer and repacker ZIPs; test each archive with isolated python -I and do not change extraction behavior / `etl/spark/fixture/initialize.py`, `etl/spark/jobs/py/common/package.py`, `tests/test_spark_documents.py`.
- Anomaly job explicitly writes both audit lake and JDBC output / matching the lake falsely marks an unproduced relation green / ship COMPAT.SPARK_ALERT_ANOMALY from the converted model and compare its counts, profiles, keys, hashes and samples to actual PostgreSQL JDBC rows; record SECURITY_ALERT as audit-assigned and SPARK_ALERT_ANOMALY as not separately manifest-assigned / `warehouse/dbt/models/spark/security_alert_anomaly/security_alert_anomaly_jdbc.sql`, `parity/spark_documents.py`, `parity/documents.json`.
- Spark anomaly computes population score moments and an explicit zero-standard-deviation fallback / sample STDDEV or new rounding changes z-scores / preserve count/sum/squared-sum arithmetic and fallback 1.0 exactly, without tolerance, on the identical audit landing / `warehouse/dbt/models/spark/security_alert_anomaly/security_alert_anomaly.sql`, `etl/spark/jobs/py/security_alert_anomaly.py`.
- Spark output is absent, stale, failed or older than an upstream lake dependency / cached artifacts masquerade as fresh parity / require input/output/log availability and freshness, record landing/output/upstream/code SHA-256s, block downstream candidates unless upstream parity passed, and reject replay evidence if any fingerprint or partition set changes / `parity/spark_documents.py`, `parity/documents_board.py`, `tests/test_documents_board.py`.
- Spark manifest output_relations are absent or classification.yaml conflicts with approved targets / candidates are unmeasured or an approved manifest is casually rewritten / keep the manifest unchanged, declare keyed lake and JDBC outputs in the subject relation contract and convert to manifest targets; inventory callers, proposed owners and shared inputs separately / `parity/documents.json`, `documents/spark_jobs.json`, `parity/documents_board.py`.
- Multiple subjects have different evidence branches and metric-code versions / documents links point to billing or billing metric ranges drift / select branch per subject and version billing's metric-source ranges with its source SHA; generate current documents ranges from AST, attach source/converted/metric/evidence links, and compare all billing rows byte-for-byte after regeneration / `parity/provenance_subjects.json`, `parity/provenance.py`, `parity/object_board.py`.
- Denied Snowflake grants and manifest retire candidates / local green is mistaken for live execution or deletion approval / attach the recorded denied preflight independently to every documents row, keep capture/prove false, and distinguish four retire candidates from ten unresolved executable objects / `parity/snowflake-preflight.json`, `parity/object_board.py`, `parity/documents_board.py`.
- Audit batch and PowerCenter share core AUDIT tables / false mapping greens from batch snapshots / execute original XML in rollback-only fresh targets and the shipped workflow against core table names in an independent proof connection; keep mapping/session/workflow measurements separate from batch / `parity/powercenter_audit.py`, `audit/50_powercenter.sql`.
- Audit reconciliation includes an out-of-manifest generic helper before the 37 BTEQ counts / missing row 21000000001 and changed self-counts / preserve helper-before-BTEQ-before-P_RECON_COUNTS order and declare external USERS/DOCUMENTS snapshot inputs separately from converted BILLING / `audit/40_reconciliation.sql`, `parity/local_audit.py`.
- Audit landing PSVs have no header / COPY SKIP_HEADER=1 loses the first record / use SKIP_HEADER=0 and header=false locally; retain archive landing after approved Teradata archive retirement / `audit/05_landing.sql`, `parity/local_audit.py`.
- Six unused audit archive objects / owner approved retirement, not conversion / match the approved names against manifest retire targets and mark retired with decision evidence; preserve Spark archive jobs and their landing feed, do not physically delete source objects during board generation / `audit/decisions.json`, `parity/owner_decisions.py`, `parity/object_board.py`.
- Spark audit inputs differ from batch audit DDL / wrong IDs, timestamps or header handling / use the actual headered Spark PSVs and Spark schemas, not batch staging snapshots; compare both lake and JDBC outputs independently / `parity/spark_audit.py`, `tools/audit_outputs.py`.
- Spark concat_ws newline over collect_list ignores null lines / login text byte counts drift for null or multibyte text / sum UTF-8 byte lengths plus max(nonnull-count minus one, zero); lower OCTET_LENGTH text through DuckDB ENCODE for local proof / `warehouse/dbt/models/spark/audit_actor_activity_join`, `parity/spark_audit.py`.
- Spark archive resort and lake compaction change physical layout only / deduplication or an invented uniqueness test loses multiset semantics / preserve all rows, compare full-row multiplicity, use dbt ref for converted lake dependencies; file count/order is not relational parity / `warehouse/dbt/models/spark/audit_archive_resort`, `warehouse/dbt/models/spark/lake_compaction_audit`.
- Teradata implicit VARCHAR width coercion on INSERT / APP_USER source core truncates 100 display names to 60 while DuckDB keeps staging's 200; Snowflake may error rather than truncate (live behavior unverified) / stop and escalate, never add truncation or hash normalization to force green; source emulator dispatch injects destination-width casts / `warehouse/teradata/ddl/users/00_tables.sql`, `warehouse/teradata/scripts/users/01_load_users.bteq`, `warehouse/teradata/bteq/runner.py`, `users/README.md`.
- PowerCenter source/SQ/transform port precision precedes expressions / STG DISPLAY_NAME truncates to 60 before TRIM while the owned model retains 200 / inspect XML and reachable runner coercion, retain measured mismatch red without model patches or hash normalization; verify email and status casing independently / `etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_STG_APP_USER.XML`, `etl/informatica/runner/engine.py`, `parity/pc_users.py`, `parity/local_content.py`.
- PowerCenter output shares a table with BTEQ / relation parity alone falsely implies mapping execution / capture initial targets, run actual workflow plus explicitly enabled standalone sessions, compare actual targets with shipped dbt SELECT plus table/merge materialization on identical inputs, restore source state, and retain supplementary BTEQ measurements; bind capture to input/code hashes / `parity/pc_users.py`, `parity/object_board.py`.
- PowerCenter LOGIN_EVENT router default group has no writer / unknown result codes disappear although BTEQ keeps all rows / prove both ordinary landing and a supplemental actual-runner probe; ordinary users landing has only SUCCESS; FAILED/LOCKED/MFA_FAILED survive and UNROUTED drops in both PC and dbt / `etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_LOGIN_EVENT.XML`, `warehouse/dbt/macros/pc_content_login_event.sql`, `users/README.md`.
- Session Truncate target table flags and disabled workflow tasks / full replacement differs from append/merge; TEAM_MEMBER is not scheduled / honor STG_APP_USER/ROLE_GRANT truncate, other three nontruncate; invoke disabled TEAM_MEMBER via startsession and disclose that scheduling was not proved / `etl/informatica/repository/SFX_CONTENT/wf_SFX_CONTENT_DAILY.XML`, `parity/pc_users.py`.
- APP_USER Use First Value lookup and update strategy / BTEQ replacement cannot prove insert/update or duplicate lookup choice / execute against captured existing targets, retain unmatched rows, report absence of duplicate lookup keys as an empirical limitation; isolated hash_difference=0 does not clear the separate APP_USER truncation hold / `etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_APP_USER.XML`, `parity/pc_users.py`, `parity/object_board.py`.
- P_ACTIVITY_DAILY and M_TEAM_COUNTS oddities / date-scoped cleanup or distinct-user counting changes source results / preserve deletion of all activity IDs >=10000000000, DOCUMENT_COUNT=0, macro ignoring p_day and counting TEAM_MEMBER_ID; preserve BTEQ secondary-table delete/insert effects and declare resultset exports / `users/10_load.sql`, `users/20_routines.sql`, `parity/report_outputs.py`.
- Spark jobs with shipped Snowpark but manifest dbt_model / rewritten stand-in cannot prove the shipped implementation / extract shipped UDF bodies and projections (including UDTF process/end_partition), run on DuckDB, reject unsupported shapes, compare actual lake Parquet on the same landing; do not silently claim a dbt materialization was run / `parity/spark_users.py`, `warehouse/snowpark/team_graph_components.py`.
- Spark JSON/browser/graph/risk defaults / missing keys, unmatched agents, graph convergence or float rounding can quietly differ / preserve missing key empty string, invalid JSON NULL and Python str, Other fallback, exactly six graph iterations with self-edges excluded, and exact logistic double computation; stop only on measured disagreement / `warehouse/snowpark/user_pref_json_flatten.py`, `warehouse/snowpark/users_login_useragent_parse.py`, `warehouse/snowpark/team_graph_components.py`, `warehouse/snowpark/users_risk_score.py`, `tests/test_spark_users.py`.
- Spark JDBC overwrite side outputs / lake parity misses SPARK_RISK_SCORE and SPARK_TEAM_ROLLUP / inspect and compare JDBC outputs independently, search manifest/registry/repository readers; these users side tables match lake but lack separate manifest declarations, and external consumers remain unverified / `etl/spark/scala/src/main/scala/sfx/UsersRiskScore.scala`, `etl/spark/jobs/py/users_team_rollup.py`, `users/README.md`.
- Make namespace validation / sfx1119-before is rejected where RunConfig generates sfx-1119-before / derive NS from RunConfig and use it consistently; do not weaken validation or silently switch estates / `warehouse/run_config.py`, `parity/pc_users.py`.
- Spark startup fixture regeneration and append outputs / stale landing evidence, UID 185 log ownership, mixed-run billing usage Parquet / pull the documented image first, restore only local runtime log ownership if needed, rerun affected jobs after landing changes; archive old append output for an explicitly initial-build proof, never deduplicate the comparison / `etl/spark/run.sh`, `parity/spark_billing.py`, `users/README.md`.
- DBQL absence and dependent retirement / pinned BEFORE evidence alone can mask new current reads; zero reads is not migrated parity / rerun assess.build(root=current checkout), require nonempty full-window DBQL, verify absence plus dead_dependents propagation and input hashes; report retire_verified separately from green, fail red, preserve licence/migration state and owner approval / `parity/retirement_users.py`, `tools/assess.py`, `parity/object_board.py`.
- Retired Teradata USER_PREF vs Spark USER_PREF / deleting the landing feed breaks retained user_pref_json_flatten / keep the independent PREF_JSON landing dependency even when Teradata PREF_NAME/PREF_VALUE tables and settings view have verified retirement evidence / `etl/spark/jobs/py/user_pref_json_flatten.py`, `parity/retirement_users.py`, `users/README.md`.
- PowerCenter session writer settings override mapping defaults / wrong rerun contents / compile owned SELECTs into area-owned users/documents session targets and have content call them, preserving truncate+insert for STG_APP_USER, ROLE_GRANT and STG_DOCUMENT and keyed merges for the remaining enabled sessions / `content/convert.py`, `users/52_sessions.sql`, `documents/52_sessions.sql`, `content/workflow.sql`.
- PowerCenter disabled task instance / standalone mapping execution incorrectly changes workflow outputs / never execute TEAM_MEMBER in content and preserve its pre-workflow table; compare all eight manifest outputs, including that untouched state / `parity/local_content.py`, `content/workflow.sql`.
- PowerCenter AND-joined success links and fail-parent tasks / premature downstream writes / run the seven sessions topologically, start DOC_SHARE only after DOCUMENT and ROLE_GRANT succeed, and propagate session SQL failures without continuing / `content/workflow.sql`, `warehouse/snowflake/pc_dag/content.yml`.
- PowerCenter two routed target instances share LOGIN_EVENT / duplicate physical-table loads / use the owned login SELECT's route consolidation once in the workflow's update-else-insert step / `content/convert.py`, `warehouse/dbt/macros/pc_content_login_event.sql`.
- Snowflake VARCHAR(n) casts versus DuckDB's ignored lengths / false downstream APP_USER differences / lower explicit shipped VARCHAR(n) casts to SUBSTRING before DuckDB execution and insert into typed target tables so NUMBER-to-BIGINT storage does not change hash types / `parity/local_content.py`.

Paths above are relative to `migration/dw-exit/` unless beginning with repository-root `warehouse/` or `etl/`.

## Parity proof for a subject area

Use the Run scope exports above and `warehouse/.venv/bin/python`. Billing and users have
independent Teradata-chain, PC and Spark proof legs. New areas need a subject registry entry,
board relation contract, faithful conversions and tests; never edit the approved manifest
to add proof relations, and do not infer PC/Spark execution from BTEQ outputs.

```sh
docker pull mirror.gcr.io/library/spark:3.5.3-scala2.12-java17-python3-ubuntu
make sfx-spark-up NS="$NS" ROWS_PER_TABLE=200
for job in billing_churn_score billing_gl_trial_balance billing_invoice_summary_daily billing_payment_aging billing_revenue_by_plan billing_usage_append_daily; do
  make sfx-spark-run NS="$NS" JOB="$job"
done
make sfx-manifest-board NS="$NS" BOARD_ROWS=200 PARITY_TARGET=duckdb
make sfx-billing-test
# Users: same landing inputs; PC capture includes initial state and restores emulator targets.
export TD_PG_PORT=$(warehouse/.venv/bin/python -c 'import os,zlib; print(54500+zlib.crc32(os.environ["NS"].encode())%1000)')
PYTHONPATH=migration/dw-exit warehouse/.venv/bin/python -m parity.pc_users --capture --namespace "$NS" --business-date 20261109 --dsn "host=127.0.0.1 port=$TD_PG_PORT dbname=teradata user=postgres"
for job in team_graph_components user_pref_json_flatten users_active_daily users_login_useragent_parse users_risk_score users_team_rollup; do
  make sfx-spark-run NS="$NS" JOB="$job" ROWS_PER_TABLE=200
done
make -o sfx-teradata-up -o warehouse/.venv/.billing-requirements sfx-manifest-board RUN_TOKEN="$RUN_TOKEN" NS="$NS" BOARD_ROWS=200 PARITY_TARGET=duckdb
warehouse/.venv/bin/python -m pytest -q migration/dw-exit/tests
# Only after read-only access preflight succeeds and no frozen baseline exists:
make sfx-billing-capture NS="$NS" BUSINESS_DATE=20261109
make sfx-billing-prove CANDIDATE=fixed BUSINESS_DATE=20261109
```

Documents proof (sfx1119, BEFORE only; Snowflake grants pending): preserve the frozen
post-BTEQ/pre-PC `migration/dw-exit/.runs/documents-pre-pc` checkpoint described in
`documents/README.md`. Do not restart/reseed source or landing before reusing outputs.

```sh
RUN_TOKEN=sfx1119 warehouse/.venv/bin/python migration/dw-exit/documents/prove_local.py \
  --pre-pc migration/dw-exit/.runs/documents-pre-pc \
  --output migration/dw-exit/.runs/documents-local.json
# On a fresh Spark fixture only, initialize once, then run all manifest documents jobs:
make sfx-spark-up NS=sfx-1119-before ROWS_PER_TABLE=200
for job in collab_session_sessionize doc_share_graph_reach doc_version_diff_stats docs_event_export_hourly docs_folder_legacy_report docs_folder_tree_walk docs_search_log_parse docs_share_activity docs_storage_by_owner docs_tag_normalize file_object_binary_extract lake_compaction_documents security_alert_anomaly; do
  make sfx-spark-run NS=sfx-1119-before ROWS_PER_TABLE=200 JOB="$job"
done
RUN_TOKEN=sfx1119 warehouse/.venv/bin/python migration/dw-exit/documents/replay_spark.py \
  --dates 2026-11-18 2026-11-19 --output migration/dw-exit/documents/spark-replay.json
RUN_TOKEN=sfx1119 warehouse/.venv/bin/python migration/dw-exit/parity/spark_documents.py \
  --output migration/dw-exit/.runs/documents-spark.json
make -o sfx-teradata-up sfx-manifest-board RUN_TOKEN=sfx1119 NS=sfx-1119-before BOARD_ROWS=200 PARITY_TARGET=duckdb
warehouse/.venv/bin/python -m pytest -q migration/dw-exit/tests
make sfx-manifest-board-test
make sfx-spark-test
```

The replay executes the actual legacy job with explicit SFX_RUN_DATE on two dates,
checks unchanged landing SHA-256s, and executes the shipped incremental DELETE/INSERT
against cumulative lake output. Board generation reruns SQL/PC/current Spark/JDBC
comparisons and validates every saved replay fingerprint before using its history metrics.
Outputs: `documents/evidence.json`, `documents/spark-replay.json`, generated
`documents/parity-table.md`, `board/board.json` and `board/README.md`. Exit zero means
a report completed, not that all objects are green. Ten documents objects remain red
on the three reviewed owner decisions; no Snowflake objects may be created while denied.

Use RunConfig's namespace consistently. Do not reinitialize source/Spark fixtures between
capture and comparison. Run the six named users jobs for users proof; the shared Spark
packager includes warehouse.run_config for documents binary extraction too.
Install missing harness packages from `migration/dw-exit/requirements.txt`
into the warehouse venv, not system Python. The APP_USER mapping's manifest Snowpark target
has no implementation; its isolated shipped-dbt proof is explicitly labeled and held red.

Use the same business date as the local BEFORE chain. Capture writes a frozen baseline;
do not recapture over an existing token baseline. Prove writes target objects. Neither
command is read-only. Do not run `sfx-billing-promote` without owner sign-off.

Live evidence lands under `migration/dw-exit/.runs/`: `capture.json`, `deploy-fixed.json`
and `billing-fixed.json` (relation counts, profiles, multiset hash deltas and query IDs).
The generated `board/board.json` and `board/README.md` preserve separate local DuckDB and
Snowflake states. Local green is not live parity, mapping execution or cutover approval.
Billing row provenance links open the source artifact, converted producer statements and
ladder count/profile/hash implementation on the work branch, with derived `#Lx-Ly` ranges.
Unavailable outputs stay red; candidate links do not mean those candidates were executed.
Spark local proof compares actual lake Parquet with an initial dbt SELECT (not dbt's
incremental materialization); landing SHA-256 hashes and build mode are in `spark_evidence`.
Outputs older than the landing inputs are rejected. Repeated append runs can legitimately
produce duplicate legacy rows; the ladder preserves duplicates rather than hiding them.
The local proof does not establish incremental rerun semantics or live Snowflake parity.

**Grant gotcha:** the provisioned role is token-scoped. Bind `SNOWFLAKE_ACCOUNT`,
`SNOWFLAKE_USER`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_PRIVATE_KEY`, `SNOWFLAKE_DATABASE` securely,
then read-only check database existence and `SHOW GRANTS ON DATABASE <run_database>` before
capture. Login success does not establish database access. For `RUN_TOKEN=sfx1119`,
`SFX_D1110_ROLE` received error `002003` on `SFX_1119`; capture/prove were not run.
Do not create the database, switch tokens or reuse another token's namespace to work around
this. The recorded denial in `parity/snowflake-preflight.json` is consumed by the board
generator (`--snowflake-preflight` selects another recorded denial); mismatched run scopes
are rejected. The board does not perform live proof or infer live success from this file.

## Local failure feed

Set `SFX_GRAFANA_PASSWORD` and `SFX_ALERT_WEBHOOK_URL` explicitly before starting:

```sh
make sfx-observability-up
```

Grafana: `http://127.0.0.1:13000`; Loki: `http://127.0.0.1:13100`.
Loader and check events: `migration/dw-exit/.runs/logs/pipeline.jsonl`.
Runner session/workflow logs are shipped from `etl/informatica/infa_shared/`.
For a local-only webhook endpoint, set the URL to `http://alert-sink:9095/sink`
and add `--profile test` to the observability Compose command. Captures land in
`migration/dw-exit/.runs/alerts/sink.jsonl` and are available at
`http://127.0.0.1:19095/sink/latest`.

Stop the feed with `make sfx-observability-down`. Stop compute with
`make sfx-spark-down NS="$NS"`. `make sfx-informatica-down NS="$NS"` and
`make sfx-teradata-down NS="$NS"` remove their namespace's local data volumes.
