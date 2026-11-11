<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# users_active_daily (Spark -> Databricks SQL serverless)

Source: `etl/spark/jobs/py/users_active_daily.py`. Target: `cpw.dbx_d1111_after.users__spark_users_active_daily`, written by `users_active_daily.sql` (sql_task on the serverless SQL warehouse; Jobs API 2.1 settings are in `job.json`).

## Commands
```sh
# deploy and run: upload users_active_daily.sql to /Workspace/Shared/dbx-d1111-spark/users_active_daily/ and create the job from job.json (warehouse_id filled in)
databricks jobs run-now 663977597238323
# inputs: run each SELECT in inputs.sql, export as PSV to <landing>/users/<TABLE>/<yyyymmdd>.psv, then
make sfx-spark-up SFX_SPARK_LANDING=<abs dir> && make sfx-spark-run JOB=users_active_daily
# parity: run parity.sql (step=parity after run 1, step=idempotence after run 2)
```

## Query history
```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=users_active_daily */%'
ORDER BY start_time
```
At write time it returned 0 rows (statement `01f1dd85-66b0-11f9-9d23-73884784ff66`). Ingestion lags 30-40 min.

## Standard settings
- Adaptive execution: serverless AQE, enabled by default. The source's executor memory/cores and fixed `spark.sql.shuffle.partitions` were removed, along with any repartition/coalesce.
- Retries: max_retries=2, min_retry_interval_millis=60000, retry_on_timeout=false, timeout_seconds=1800.
- Partition sizing: Delta table with no partitioning or CLUSTER BY; no downstream contract needs either.
- Idempotent write: `CREATE OR REPLACE TABLE ... AS SELECT`. Run 2 gave the same count, hash and `numOutputRows`.
- Schedule: none (orchestration is combined later). Tags: run_token=dbx-d1111, expires=2026-11-24, act=spark.

## Board row
| field | value |
|---|---|
| source | `etl/spark/jobs/py/users_active_daily.py` |
| target | `cpw.dbx_d1111_after.users__spark_users_active_daily` |
| first failure | inputs: landing USER_ACTIVITY_DAILY.ACTION_COUNT (summed into ACTIONS) has no live column; only document_count exists (0 rows) `01f1dd85-2121-165c-92a1-80e96955ad3d` |
| corrected parity | count 3/3, hash equal, 0/0 EXCEPT ALL `01f1dd85-0e61-15aa-9b97-90e6f3ee6030` |
| idempotence | run2 count 3, hash 2285680851598220970 unchanged, numOutputRows unchanged `01f1dd85-344e-1fcd-a220-034dede87ff9, 01f1dd85-34dd-185f-adb4-3b4e941ab0d0, 01f1dd85-3634-1337-8205-6fbf4a576183` |
| job_id / run_ids | 663977597238323 / 371487412093422, 458260274520407 |
| executor-hours before | 0.002261111 (baseline app `app-20261110202428-0006`; parity run app `app-20261111040131-0003`) |
| DBU after | 371487412093422: PENDING, 458260274520407: PENDING (billing statement `01f1dd85-692f-121f-8c53-a6ee0aead456`; different unit from executor-hours) |
| status | RED |

## Red reason
`USER_ACTIVITY_DAILY.ACTION_COUNT` has no live equivalent. The live `users__user_activity_daily` has only `document_count`, which `warehouse/teradata/procedures/activity_daily.sql` fills with a document count, not an action count. `ACTIONS` is NULL on both sides, so parity cannot validate that column. The other columns match.
