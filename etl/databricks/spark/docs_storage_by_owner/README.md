<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# docs_storage_by_owner (Spark -> Databricks SQL serverless)

Source: `etl/spark/jobs/py/docs_storage_by_owner.py`. Target: `cpw.dbx_d1111_after.documents__spark_docs_storage_by_owner`, written by `docs_storage_by_owner.sql` (sql_task on the serverless SQL warehouse; Jobs API 2.1 settings are in `job.json`).

## Commands
```sh
# deploy and run: upload docs_storage_by_owner.sql to /Workspace/Shared/dbx-d1111-spark/docs_storage_by_owner/ and create the job from job.json (warehouse_id filled in)
databricks jobs run-now 237874230352071
# inputs: run each SELECT in inputs.sql, export as PSV to <landing>/documents/<TABLE>/<yyyymmdd>.psv, then
make sfx-spark-up SFX_SPARK_LANDING=<abs dir> && make sfx-spark-run JOB=docs_storage_by_owner
# parity: run parity.sql (step=parity after run 1, step=idempotence after run 2)
```

## Query history
```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=docs_storage_by_owner */%'
ORDER BY start_time
```
At write time it returned 3 rows (statement `01f1dd85-5b10-17f4-939f-9f93ee566da6`). Ingestion lags 30-40 min.

## Standard settings
- Adaptive execution: serverless AQE, enabled by default. The source's executor memory/cores and fixed `spark.sql.shuffle.partitions` were removed, along with any repartition/coalesce.
- Retries: max_retries=2, min_retry_interval_millis=60000, retry_on_timeout=false, timeout_seconds=1800.
- Partition sizing: Delta table with no partitioning or CLUSTER BY; no downstream contract needs either.
- Idempotent write: `CREATE OR REPLACE TABLE ... AS SELECT`. Run 2 gave the same count, hash and `numOutputRows`.
- Schedule: none (orchestration is combined later). Tags: run_token=dbx-d1111, expires=2026-11-24, act=spark.

## Board row
| field | value |
|---|---|
| source | `etl/spark/jobs/py/docs_storage_by_owner.py` |
| target | `cpw.dbx_d1111_after.documents__spark_docs_storage_by_owner` |
| first failure | none: first comparison matched `-` |
| corrected parity | count 200/200, hash equal, 0/0 EXCEPT ALL `01f1dd85-00c0-18f1-abfd-3ad3113b5ba9` |
| idempotence | run2 count 200, hash 120678440621456755338 unchanged, numOutputRows unchanged `01f1dd85-2b05-1c91-af5a-d0d5abe9b890, 01f1dd85-2b9e-1e9d-85c5-07f6a39a3ca2, 01f1dd85-2d06-1a75-abdb-70177368f148` |
| job_id / run_ids | 237874230352071 / 1104480994257569, 284880459397735 |
| executor-hours before | 0.002620833 (baseline app `app-20261110202403-0004`; parity run app `app-20261111040039-0000`) |
| DBU after | 1104480994257569: PENDING, 284880459397735: PENDING (billing statement `01f1dd85-5d67-1997-a423-a241c17943d0`; different unit from executor-hours) |
| status | GREEN |
