<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# users_team_rollup (Spark -> Databricks SQL serverless)

Source: `etl/spark/jobs/py/users_team_rollup.py`. Target: `cpw.dbx_d1111_after.users__spark_users_team_rollup`, written by `users_team_rollup.sql` (sql_task on the serverless SQL warehouse; Jobs API 2.1 settings are in `job.json`).

## Commands
```sh
# deploy and run: upload users_team_rollup.sql to /Workspace/Shared/dbx-d1111-spark/users_team_rollup/ and create the job from job.json (warehouse_id filled in)
databricks jobs run-now 627663219394880
# inputs: run each SELECT in inputs.sql, export as PSV to <landing>/users/<TABLE>/<yyyymmdd>.psv, then
make sfx-spark-up SFX_SPARK_LANDING=<abs dir> && make sfx-spark-run JOB=users_team_rollup
# parity: run parity.sql (step=parity after run 1, step=idempotence after run 2)
```

## Query history
```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=users_team_rollup */%'
ORDER BY start_time
```
At write time it returned 1 rows (statement `01f1dd85-6ad6-1956-926f-17dcdc745d4b`). Ingestion lags 30-40 min.

## Standard settings
- Adaptive execution: serverless AQE, enabled by default. The source's executor memory/cores and fixed `spark.sql.shuffle.partitions` were removed, along with any repartition/coalesce.
- Retries: max_retries=2, min_retry_interval_millis=60000, retry_on_timeout=false, timeout_seconds=1800.
- Partition sizing: Delta table with no partitioning or CLUSTER BY; no downstream contract needs either.
- Idempotent write: `CREATE OR REPLACE TABLE ... AS SELECT`. Run 2 gave the same count, hash and `numOutputRows`.
- Schedule: none (orchestration is combined later). Tags: run_token=dbx-d1111, expires=2026-11-24, act=spark.

## Board row
| field | value |
|---|---|
| source | `etl/spark/jobs/py/users_team_rollup.py` |
| target | `cpw.dbx_d1111_after.users__spark_users_team_rollup` |
| first failure | none: first comparison matched `-` |
| corrected parity | count 20/20, hash equal, 0/0 EXCEPT ALL `01f1dd85-1216-1aa8-a09e-5181c66833fa` |
| idempotence | run2 count 20, hash 11391394300865053031 unchanged, numOutputRows unchanged `01f1dd85-371c-1447-bc0c-b731c1a76cc8, 01f1dd85-37a7-15d6-b5b0-f146c16bde48, 01f1dd85-3931-182a-88f4-fd60c6ba0673` |
| job_id / run_ids | 627663219394880 / 310705676502933, 1091308681060894 |
| executor-hours before | 0.003556111 (baseline app `app-20261110202437-0007`; parity run app `app-20261111040145-0004`) |
| DBU after | 310705676502933: PENDING, 1091308681060894: PENDING (billing statement `01f1dd85-6ccc-169e-a42c-bee956dc1720`; different unit from executor-hours) |
| status | GREEN |

## Note
The source also overwrote the JDBC table `sfx_users.SPARK_TEAM_ROLLUP`. The Delta target replaces it; repoint any reader of that table.
