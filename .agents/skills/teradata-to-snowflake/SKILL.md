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

## Billing conversion lessons (sfg1120)

Learned taking every billing manifest object to green on the local DuckDB board
(`migration/dw-exit/billing/chain.yaml` replays the daily chain; Snowflake stays red while its login is down).

- **CHAR padding and widths.** `INSERT ... SELECT *` from a `STG_` table drops Teradata semantics:
  load with explicit columns, `RPAD(col, n)` for `CHAR(n)` and `LEFT(col, n)` for `VARCHAR(n)` targets.
- **NOT CASESPECIFIC.** Teradata joins, groups and partitions these columns case-insensitively and
  ignores trailing blanks. Use `UPPER(RTRIM(col))` in `ON`, `GROUP BY` and `PARTITION BY`, and
  `MIN(RTRIM(col))` for the displayed value. Teradata returns an arbitrary member's case for such a
  group (`usd` vs `USD`), so exports compare those keys case-folded (`case_folded` in `chain.yaml`).
- **Dates.** `CAST(d AS FORMAT 'YYYY-MM')` is `TO_CHAR(d, 'YYYY-MM')`, never `LEFT(TO_CHAR(d), 7)`.
  `CAST(d AS INTEGER) + 19000000` is `YEAR(d)*10000 + MONTH(d)*100 + DAY(d)`, not a day count.
  `BETWEEN ${PERIOD_START_INT} AND ${PERIOD_END_INT}` is the previous calendar month:
  `>= DATEADD(month, -1, DATE_TRUNC(month, run_day)) AND < DATE_TRUNC(month, run_day)`.
- **Monthly journal.** `12_invoice_monthly` deletes only the current month's `GL_JOURNAL_LINE` window and
  prefixes ids with `YYYYMM * 1e12` (credit notes add `5e11`); the procedure itself writes no journal lines.
  `01_load_accounts` also appends staged journal lines for posting dates not yet in the ledger.
- **sqlglot to DuckDB.** sqlglot drops the format of `TO_CHAR(d, 'YYYY-MM')` (emits `CAST(d AS TEXT)`) and
  leaves literal `TO_DATE(s, fmt)` untranslated; the board's `to_duckdb()` rewrites both to
  `STRFTIME`/`STRPTIME`. Re-check any new format-sensitive function locally.
- **Snapshots.** An unconstrained PostgreSQL `NUMERIC` (a view's `SUM`) has no catalog scale; take the scale
  from the values or the before side rounds to integers.
- **Spark.** JDBC reads from the emulator return lower-case column names; compare column names upper-cased
  (Snowflake folds unquoted identifiers). Python/JVM `exp()` and DuckDB/Snowflake `EXP()` differ in the last ULP,
  so DOUBLE values compare at 12 significant digits. `billing_usage_append_daily` matches the dbt model's
  incremental branch; the first full build backfills every date on purpose.

```sh
export RUN_TOKEN=sfx-sfg1120 NS=sfx-sfg1120-before
make sfx-teradata-up NS="$NS" ROWS_PER_TABLE=200
uv run --python 3.11 --with pyspark==3.5.3 --with pyyaml==6.0.2 python migration/dw-exit/parity/spark_local.py
make sfx-manifest-board NS="$NS" PARITY_TARGET=duckdb   # board.json + board/billing.html
```

`board.json` `capacity_estimate` prices each workload on its X-Small warehouse from
`warehouse/snowflake/capacity.py`: max(DuckDB seconds, 60 s minimum) plus the 60 s auto-suspend tail, 1 credit/hour.
