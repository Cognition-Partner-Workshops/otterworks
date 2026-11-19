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
- Teradata SET table silently drops exact-duplicate rows on INSERT…SELECT / target MULTISET-equivalent table keeps them (STORAGE_USAGE_DAILY 250 vs 300 rows at ROWS_PER_TABLE=200), inflating storage totals and billing storage charges / never add or omit `DISTINCT` on your own: carry the INSERT unchanged, mark the table and every reader red as an owner decision / `documents/10_load.sql` (`05_LOAD_SESSIONS`), `parity/local_documents.py` `OWNER_DECISIONS`.
- `QUALIFY ROW_NUMBER() … ORDER BY` on a non-unique column / Teradata and Snowflake pick different rows among ties, so counts match while keyed hashes differ / carry the ORDER BY unchanged, do not invent a tie-break, keep the script and its downstream views red until the owner names the secondary key / `documents/10_load.sql` (`02_CURRENT_VERSIONS`).
- PowerCenter lookup "Use First Value" on a non-unique lookup key / a plain LEFT JOIN fans out and any chosen row is a precedence decision / the fixture has one grant per user so measured parity cannot prove the rule; keep mapping and session red until role precedence is decided / `warehouse/dbt/models/pc/content/pc_content__doc_share.sql`.
- PowerCenter targets live in the runner's own warehouse database, not the Teradata snapshot / comparing a mapping against the BTEQ-loaded table of the same name measures the wrong producer / snapshot the runner database into a separate `PC_BEFORE` schema and build the dbt models from the same landing PSVs / `parity/local_documents.py` `powercenter`.
- TPT LOAD operators into staging / stage rows untyped or missing / `COPY INTO RAW_<AREA>` (existing loader procedure) then one typed `INSERT … SELECT` per TPT script with explicit `TO_DATE`/`TO_TIMESTAMP_NTZ` formats / `documents/05_stage.sql`.
- Teradata `UNIQUE PRIMARY INDEX` / Snowflake `PRIMARY KEY` is informational, duplicates load without error / declare the key for lineage and rely on row-hash parity, not the constraint, to detect duplicates / `documents/00_tables.sql`.
- `LOCKING ROW FOR ACCESS` view prefix / no Snowflake counterpart / drop it; view-on-view references point at the `COMPAT` view, not the base table / `documents/30_views.sql`.
- A BTEQ that crosses subject areas (documents `10_storage_monthly` writes billing tables) / double conversion or unmeasured writes / keep the SQL with the area that owns the target tables and ship only the remaining export in the calling area; the row compares both the billing relations and the macro resultset / `documents/20_routines.sql`, `billing/15_storage.sql`.
- Retire candidates / dropping an object that is still read / confirm against `warehouse/teradata/dbql` (`qrylog.csv` joined to `objectusage.csv`) and record window, read count and readers on the row; any read blocks the retirement (STG_SEARCH_INDEX_LOG has one read by `svc_report_recon`), zero reads still needs owner approval before a drop / `parity/local_documents.py` `retirement`.
- Spark output partitioned by a column (`EXPORT_BUCKET=n/`) or written under another area's lake path / legacy output reported missing / read `lake/*/<job>/**/*.parquet` with hive partitioning / `parity/spark_billing.py`.
- Spark jobs whose shipped target is Snowpark Python or retained Spark / no SQL body to run on DuckDB / link the shipped code and leave the row red as unmeasured; do not rewrite the logic in SQL just to turn the row green / `parity/spark_billing.py`.

Paths above are relative to `migration/dw-exit/` unless beginning with `warehouse/`.

## Parity proof for a subject area

Use the Run scope exports above and `warehouse/.venv/bin/python`. Billing and documents are implemented
(`parity/local_billing.py`, `parity/local_documents.py`); other areas need their own conversions and materializer.
Set `SFX_PROVENANCE_REF` to the branch the board links should open on (default `devin/sfx1119-billing-parity`).
Documents also needs every Spark job run (`make sfx-spark-run NS="$NS"`) and the PowerCenter content workflow
(`make sfx-informatica-up NS=sfx1119_docs && make sfx-informatica-run NS=sfx1119_docs MAPPINGS=all INFA_WORKFLOWS=SFX_CONTENT:wf_SFX_CONTENT_DAILY`;
override with `PC_NS` or `PC_SOURCE_DSN`). Without them those rows are red as unmeasured.

```sh
make sfx-spark-up NS="$NS" ROWS_PER_TABLE=200
for job in billing_churn_score billing_gl_trial_balance billing_invoice_summary_daily billing_payment_aging billing_revenue_by_plan billing_usage_append_daily; do
  make sfx-spark-run NS="$NS" JOB="$job"
done
make sfx-manifest-board NS="$NS" BOARD_ROWS=200 PARITY_TARGET=duckdb
make sfx-billing-test
# Only after read-only access preflight succeeds and no frozen baseline exists:
make sfx-billing-capture NS="$NS" BUSINESS_DATE=20261109
make sfx-billing-prove CANDIDATE=fixed BUSINESS_DATE=20261109
```

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
