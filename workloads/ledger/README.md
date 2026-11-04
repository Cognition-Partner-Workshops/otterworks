# Consumption ledger

What each workload on the shared Snowflake account cost to build (phase `dev`) and to run (phase `runtime`),
read from `SNOWFLAKE.ACCOUNT_USAGE` alone and joined on the `csid`, `phase` and `commit` keys of each query's
`QUERY_TAG`.

- [`consumption_ledger.sql`](consumption_ledger.sql) is the query. Statement 1 is the ledger (one row per csid seen
  in `QUERY_HISTORY` tags or in a `DEVIN_CSID` warehouse tag), 2 the view watermarks, 3 untagged queries on workload
  warehouses, 4 registered csids running off their own warehouse.
- [`run_ledger.py`](run_ledger.py) runs it with key-pair auth and writes [`output/`](output/):
  [`ledger.md`](output/ledger.md), `ledger.csv` (full 40-character commits, query and session counts, credits landed
  so far), `watermarks.csv`, `labeling_gaps.csv`, `off_warehouse.csv`.

```bash
SNOWFLAKE_ACCOUNT=... SNOWFLAKE_USER=... SNOWFLAKE_ROLE=... SNOWFLAKE_PRIVATE_KEY_FILE=/path/key.p8 \
  uv run --with snowflake-connector-python==4.8.1 python workloads/ledger/run_ledger.py
```

## Reading the columns

- `dev_credits`, `runtime_credits`: `QUERY_ATTRIBUTION_HISTORY` compute plus query acceleration for the csid's
  queries in that phase. `pending` until the view's newest row passes the csid's last query in that phase. Pending
  is not zero; `*_credits_landed` in `ledger.csv` is the partial figure behind a `pending`.
- `cortex_ai_credits`: `CORTEX_AI_FUNCTIONS_USAGE_HISTORY` joined on `query_id`, same rule against its hourly buckets.
- `warehouse_metered_credits`: `WAREHOUSE_METERING_HISTORY` for the warehouse whose `DEVIN_CSID` tag names the csid,
  closed hours only, through `metering_through`. It includes idle time and every query on that warehouse, tagged or
  not, so it is the ceiling of what the warehouse cost, not a dev/runtime split. `n/a` when no warehouse carries the
  csid.
- `stage`: `runtime` once any query tagged `phase=runtime` exists, else `dev`.
- `dev_commits`, `runtime_commits`: every distinct 40-hex `commit` in the tags, in first-seen order.

## What the ledger proves

- Every row's queries, phase and commit come from Snowflake's own `QUERY_HISTORY`; no repo file or PR text is read.
- The three workloads in `workloads/index.yaml` on the attribution branches (`cs_doc_usage_dashboard_account_usage`,
  `cs_doc_search_api_top_items`, `cs_churn_model_account_score`) are the only csids registered by a `DEVIN_CSID`
  warehouse tag, each on its own `SFNFR_20261104_WH_*` warehouse, and each has dev and runtime queries.
- The metered cost of each registered warehouse, through the metering watermark, and which commits ran on it.
- Which credit figures have not landed yet: every attributed figure in this run is `pending`, because
  `QUERY_ATTRIBUTION_HISTORY` stops hours before the workloads ran.
- The labeling gaps themselves (`labeling_gaps.csv`, `off_warehouse.csv`): untagged Streamlit runtime, `SYSTEM`
  task and viewer queries on workload warehouses, platform migrations tagged with a `schemachange` prefix and no
  csid, and registered csids that also ran on `DEVIN_WH`, `SFNFR_20261104_WH_MIGRATIONS` or other runs' warehouses.

## What it cannot prove

- That `Devin_Demo` is a real application. It is the free-text `APPLICATION` the client sends at connect time,
  recorded in `SESSIONS.CLIENT_ENVIRONMENT`. Snowflake has no registry of application names, and `Devin_Demo` is not
  registered anywhere: other clients on the account send `PythonSnowpark` or `Devin_Demo_cs_probe02`, and nothing
  stops any client from sending `Devin_Demo`. Many sessions have also not landed in `SESSIONS` yet.
- That a csid, phase or commit is true. Tags are client-set strings. Several unregistered rows carry the all-zero or
  `0123456789ab...` placeholder SHA, and some SHAs are not in this repository; checking a commit against git, a PR or
  a Devin session is outside Snowflake.
- Who a csid belongs to when no warehouse is tagged with it: unregistered rows are probes, smoke tests and other
  migrations sharing the account, listed so every csid seen has a row, not workloads in this repo.
- How to split a warehouse's metered credits between tagged queries, untagged queries and idle time before
  `QUERY_ATTRIBUTION_HISTORY` lands, nor afterwards for untagged queries (Streamlit and task runtimes do not carry the
  session `QUERY_TAG`).
- The cost of the shared platform work (`schemachange` migrations tagged `workload=platform` without a csid, role
  and grant setup on `DEVIN_WH`): it is real build cost with no csid to land on.
- Storage, serverless task and Snowpark Container Services spend: those views are keyed by object, not by query tag.
