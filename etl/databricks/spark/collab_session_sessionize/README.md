# collab_session_sessionize → Databricks serverless

Source: `etl/spark/jobs/py/collab_session_sessionize.py`. Target: `cpw.dbx_d1111_after.documents__spark_collab_session_sessionize` via Databricks SQL (`sql_task` file on the serverless warehouse).

`groupByKey` + Python sort/split re-expressed with window functions: per (USER_ID, DOCUMENT_ID) a new session starts when the gap to the previous event is > 1800 s (microsecond precision, as `total_seconds()`); SESSION_NUMBER from 1; START_AT/END_AT = first/last event. NULL semantics kept: a single NULL event gives one NULL session; NULLs in a multi-event group fail (`sorted()` raises) via `raise_error`. The SQL file inlines `inputs.sql`; job-executed statements carry `step=job` (a SQL file cannot take the step as a comment parameter).

Inputs (`inputs.sql`): documents__collab_session → COLLAB_SESSION (session_id → COLLAB_SESSION_ID, start_ts → EVENT_AT, SESSION_ID NULL). Every live row has start_ts = end_ts (2000/2000, `01f1dd84-84e9-14a2-9bef-0d2d4b760fce`). Live adapter hash = Spark landing hash (1151486316017072461598).

## Board row
| field | value |
| --- | --- |
| source | `etl/spark/jobs/py/collab_session_sessionize.py` |
| target | `cpw.dbx_d1111_after.documents__spark_collab_session_sessionize` |
| first failure | Job run 24104497103694 FAILED: column list not allowed in CREATE OR REPLACE TABLE AS SELECT (RTAS); fixed with typed CASTs in the SELECT (`see query history`) |
| corrected parity | 1200 = 1200 rows, hash 669533277108376373710 both sides, EXCEPT ALL 0/0 — `01f1dd87-1212-1683-8c40-764d49599a76` (diffs `01f1dd87-12c9-1229-97bf-b6bb56aa5be3`, `01f1dd87-1325-118b-bd56-4b41adcec711`) |
| idempotence | run2: 1200 rows, same hash, numOutputRows 1200 → 1200 — `01f1dd87-9847-1052-89dd-d5f7640248e1`, `01f1dd87-99c0-1f93-9a74-516d025812a8` |
| job_id / run_ids | 514823186668830 / 24104497103694 (failed), 856828463402524, 1049890104400595 |
| before (local, live inputs) | app-20261111040213-0002: 5.2 s, 2 executors / 4 cores, 0 failed tasks, 0 spill |
| executor-hours before (History Server baseline) | 0.002546944 (app-20261110202821-0024) |
| DBU after | PENDING (see billing query) |
| status | green |

## Standard settings
- Adaptive execution: serverless AQE (default on). Reading `spark.sql.adaptive.enabled` from a serverless job raises `CONFIG_NOT_AVAILABLE`; the job logs that value instead of failing. The source's `--executor-memory/--executor-cores/--total-executor-cores/spark.default.parallelism, spark.shuffle.memoryFraction` and the fixed `HashPartitioner(4)`-style partitioning are removed; no repartition/coalesce.
- Retries: task `max_retries=2`, `min_retry_interval_millis=60000`, `retry_on_timeout=false`, `timeout_seconds=1800`; job `timeout_seconds=3600`, `max_concurrent_runs=1`, no schedule.
- Partition sizing: unpartitioned Delta, no CLUSTER BY (small full-refresh output, no downstream layout contract).
- Idempotent write: `CREATE OR REPLACE TABLE ... AS SELECT` (full refresh, same as the source `mode("overwrite")`).
- Tags: job and runs `run_token=dbx-d1111 expires=2026-11-24 act=spark`; table COMMENT + TBLPROPERTIES carry the same.

## Commands
```sh
# deploy: import files under /Workspace/Shared/dbx-d1111-spark/collab_session_sessionize/ (workspace/import, format RAW), then
#   jobs/create (or jobs/reset) with job.json (replace ${DATABRICKS_WAREHOUSE_ID})
# run: POST /api/2.1/jobs/run-now {"job_id": <id>}
# parity: run parity.sql statements on the warehouse (each statement already starts with the run comment)
# local check (inside the spark-master container of `make sfx-spark-up`, landing = live adapted PSVs):
#   LANDING_DIR=/opt/landing LAKE_DIR=/opt/lake PYTHONPATH=/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip:. python3 test_collab_session_sessionize.py
```

## Query history
```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=collab_session_sessionize */%'
ORDER BY start_time;
```

## Billing
```sql
SELECT usage_date, usage_metadata.job_id, usage_metadata.job_run_id, sku_name, sum(usage_quantity) AS dbu
FROM system.billing.usage
WHERE usage_metadata.job_id = '514823186668830'
GROUP BY ALL ORDER BY usage_date;
```
Rows lag hours; missing rows are PENDING, not zero. Executor-hours (before) and DBUs (after) are different units.
