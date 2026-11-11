<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# docs_share_activity (Spark -> Databricks SQL serverless)

Source: `etl/spark/scala/src/main/scala/sfx/DocsShareActivity.scala`. Target: `cpw.dbx_d1111_after.documents__spark_docs_share_activity`, written by `docs_share_activity.sql` (sql_task on the serverless SQL warehouse; Jobs API 2.1 settings are in `job.json`).

## Commands
```sh
# deploy and run: upload docs_share_activity.sql to /Workspace/Shared/dbx-d1111-spark/docs_share_activity/ and create the job from job.json (warehouse_id filled in)
databricks jobs run-now 14491151277670
# inputs: run each SELECT in inputs.sql, export as PSV to <landing>/documents/<TABLE>/<yyyymmdd>.psv, then
make sfx-spark-up SFX_SPARK_LANDING=<abs dir> && make sfx-spark-run JOB=docs_share_activity
# parity: run parity.sql (step=parity after run 1, step=idempotence after run 2)
```

## Query history
```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=docs_share_activity */%'
ORDER BY start_time
```
At write time it returned 1 rows (statement `01f1dd85-5f0d-1c65-b318-24e66efb6e3f`). Ingestion lags 30-40 min.

## Standard settings
- Adaptive execution: serverless AQE, enabled by default. The source's executor memory/cores and fixed `spark.sql.shuffle.partitions` were removed, along with any repartition/coalesce.
- Retries: max_retries=2, min_retry_interval_millis=60000, retry_on_timeout=false, timeout_seconds=1800.
- Partition sizing: Delta table with no partitioning or CLUSTER BY; no downstream contract needs either.
- Idempotent write: `CREATE OR REPLACE TABLE ... AS SELECT`. Run 2 gave the same count, hash and `numOutputRows`.
- Schedule: none (orchestration is combined later). Tags: run_token=dbx-d1111, expires=2026-11-24, act=spark.

## Board row
| field | value |
|---|---|
| source | `etl/spark/scala/src/main/scala/sfx/DocsShareActivity.scala` |
| target | `cpw.dbx_d1111_after.documents__spark_docs_share_activity` |
| first failure | none: first comparison matched `-` |
| corrected parity | count 539/539, hash equal, 0/0 EXCEPT ALL `01f1dd85-04d5-19cb-8280-39ff2f235a02` |
| idempotence | run2 count 539, hash 315302314008523873440 unchanged, numOutputRows unchanged `01f1dd85-2e1c-1550-9799-24dce03524f9, 01f1dd85-2ed5-11c6-84cc-66b6fddb2834, 01f1dd85-3060-14e7-844a-545f225fef64` |
| job_id / run_ids | 14491151277670 / 735838668956230, 572040926475562 |
| executor-hours before | 0.015369167 (baseline app `app-20261110202412-0005`; parity run app `app-20261111040054-0001`) |
| DBU after | 735838668956230: PENDING, 572040926475562: PENDING (billing statement `01f1dd85-612c-149a-9db9-f99f714eb72a`; different unit from executor-hours) |
| status | GREEN |
