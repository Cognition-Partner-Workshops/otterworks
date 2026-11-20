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
export RUN_TOKEN=sfx-sfg1120
eval "$(python3 warehouse/run_config.py env)"
export NS="$RUN_BEFORE_NAMESPACE"
```

## Conversion rules

- Local `RUN_TOKEN` must have an `sfx` prefix; a branch/commit tag such as `sfg1120`
  is separate. Use the namespace printed by `warehouse/run_config.py env`.
- Users DISPLAY_NAME is owner-approved at VARCHAR(200), including APP_USER and PC
  outputs. Retain raw mismatch metrics; approve only unchanged keys/counts, legacy
  `LEFT(new,60)` names and hash-equal non-name columns under existing CHAR rules.
- PC string port precision slices before expressions; preserve slice/trim/case order,
  date/numeric coercion and reject/drop paths, not just declared target widths.
- Disabled workflow sessions stay disabled in schedules. A standalone mapping proof
  or broad dbt folder build is not workflow parity; check selectors and task DAGs.
- Prove Snowpark with `Session.builder.config("local_testing", True).create()` on
  captured PC inputs against actual runner outputs through the local ladder. This
  is not live Snowflake certification: use no credentials and keep that board leg red.
- Confirm SET versus MULTISET and lookup-source keys before inferring duplicate
  suppression or first-match nondeterminism. Inventory JDBC side outputs separately.

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

- sfg1120 owner: parity ignores trailing ASCII blanks only on DDL-declared CHAR columns; VARCHAR stays exact (`sfg1120-char-trailing-padding`).
- sfg1120 owner: LOGIN_EVENT keeps every row (BTEQ semantics); retire the PowerCenter router drop.
- sfg1120 owner: retain STG_SEARCH_INDEX_LOG and documents_search_index_log until Finance agrees an alternative.
- sfg1120 owner: retire V_SEARCH_HISTORY and SEARCH_INDEX_LOG together, dropping the view before the table.
- sfg1120 owner: retire USER_PREF, STG_USER_PREF, users_user_pref and V_USER_SETTINGS; preserve the Spark PREF_JSON landing feed.
- sfg1120 owner: storage amber extends to 10_storage_monthly, SFX_BILLING.USAGE_DAILY and SFX_BILLING.INVOICE_LINE pending Finance invoice confirmation.
- These decisions are registered in `parity/owner_decisions.py`; held-back area overrides remain authoritative until each area's engineering fixes land. Board generation never performs physical drops.

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

## Audit-learned rules

- Derive namespaces with `warehouse/.venv/bin/python warehouse/run_config.py env`.
  Run sfg1120 uses `RUN_TOKEN=sfx-sfg1120`, not the invalid token `sfg1120`.
- Keep batch, PowerCenter, and Spark evidence separate. Run the audit PC workflow,
  then the batch chain before snapshotting: PC summary appends would otherwise
  contaminate the batch baseline. PC proof executes original mappings in a fresh,
  rollback-only PostgreSQL schema on the same PSVs.
- Summary IDs follow the owner's explicit date/key contract: starting 50001,
  `ORDER BY SUMMARY_DT, CUSTOMER_ID NULLS FIRST`. Retain the raw first-seen
  sequence comparison; mismatches are approved deviations, not raw green parity.
- Staging archive is not unused: DBQL includes a setup-day `svc_report_recon`
  `COUNT(*)`. Attach that evidence to all six approved retirements; never remove
  Spark archive inputs or physically delete data during local board generation.
- Audit reconciliation reads external users, documents, and billing snapshots.
  Label these as inputs, not proof of those areas' conversions. Preserve the
  generic storage reconciliation write before audit BTEQ counts.
- Spark evidence must include all five fresh audit lake outputs and both JDBC
  outputs. Check input hashes and output freshness; compaction consumes the
  converted daily-summary dependency. Keep duplicate multiplicity and UTF-8 byte
  semantics. Unknown SQL/templates fail closed.
- Regenerate the board only with `make -o sfx-teradata-up sfx-manifest-board`
  (`BOARD_ROWS=200 PARITY_TARGET=duckdb`). Do not run a Snowflake preflight for
  a local-only run. Use `env -u NS` for standalone Informatica tests; nested
  make may additionally inherit its recipe's NS through MAKEFLAGS.
