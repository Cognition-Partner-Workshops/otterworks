---
name: teradata-to-snowflake
description: Start and verify the local warehouse, PowerCenter, Spark, dbt and DuckDB tooling.
---

# Local estate mechanics

Run commands from the repository root. Use an estate checkout containing the Spark baseline
and manifest-board changes; the board targets and legacy Spark sources are supplied there.
Requires Docker Compose, Python 3.11+, uv and Java 21 for Spark tests.

## Run scope

```sh
export RUN_TOKEN=sfxg1120
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
- Unconstrained NUMERIC aggregate metadata / rounded BEFORE totals / derive decimal scale from actual source values rather than defaulting missing scale to zero; reject unsupported precision instead of silently rounding / `parity/semantics.py`, `parity/object_board.py`.
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

Paths above are relative to `migration/dw-exit/` unless beginning with `warehouse/`.

- PowerCenter target proof must evaluate the shipped dbt SQL against the same pre-workflow tables and landing PSVs, applying explicit source truncation, lookup defaults, update semantics and sequence start; workflow success alone is not parity. Run each proof with fresh sequence state. Unordered first-match lookup or sequence ordering differences remain red rather than deduped away / `parity/pc_billing.py`, `warehouse/dbt/models/pc/billing/`.

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
