<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# docs_folder_legacy_report (Spark -> Databricks SQL serverless)

Source: `etl/spark/jobs/py/docs_folder_legacy_report.py`. Target: `cpw.dbx_d1111_after.documents__spark_docs_folder_legacy_report`, written by `docs_folder_legacy_report.sql` (sql_task on the serverless SQL warehouse; Jobs API 2.1 settings are in `job.json`).

## Commands
```sh
# deploy and run: upload docs_folder_legacy_report.sql to /Workspace/Shared/dbx-d1111-spark/docs_folder_legacy_report/ and create the job from job.json (warehouse_id filled in)
databricks jobs run-now 596114586206524
# inputs: run each SELECT in inputs.sql, export as PSV to <landing>/documents/<TABLE>/<yyyymmdd>.psv, then
make sfx-spark-up SFX_SPARK_LANDING=<abs dir> && make sfx-spark-run JOB=docs_folder_legacy_report
# parity: run parity.sql (step=parity after run 1, step=idempotence after run 2)
```

## Query history
```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status
FROM system.query.history
WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=docs_folder_legacy_report */%'
ORDER BY start_time
```
At write time it returned 3 rows (statement `01f1dd85-62f5-11a7-9649-b78356437a90`). Ingestion lags 30-40 min.

## Standard settings
- Adaptive execution: serverless AQE, enabled by default. The source's executor memory/cores and fixed `spark.sql.shuffle.partitions` were removed, along with any repartition/coalesce.
- Retries: max_retries=2, min_retry_interval_millis=60000, retry_on_timeout=false, timeout_seconds=1800.
- Partition sizing: Delta table with no partitioning or CLUSTER BY; no downstream contract needs either.
- Idempotent write: `CREATE OR REPLACE TABLE ... AS SELECT`. Run 2 gave the same count, hash and `numOutputRows`.
- Schedule: none (orchestration is combined later). Tags: run_token=dbx-d1111, expires=2026-11-24, act=spark.

## Board row
| field | value |
|---|---|
| source | `etl/spark/jobs/py/docs_folder_legacy_report.py` |
| target | `cpw.dbx_d1111_after.documents__spark_docs_folder_legacy_report` |
| first failure | inputs: landing FOLDER.PARENT_FOLDER_ID (an output column) has no live column in documents__folder/documents__stg_folder (0 rows) `01f1dd85-20bb-11b5-a032-11991dadd354` |
| corrected parity | count 200/200, hash equal, 0/0 EXCEPT ALL `01f1dd85-0999-1497-b57b-07ee9b34a9a7` |
| idempotence | run2 count 200, hash 106038821666738473275 unchanged, numOutputRows unchanged `01f1dd85-31a7-1c63-9303-e90c5c397464, 01f1dd85-3242-19c9-b5bb-c598502a737b, 01f1dd85-33b9-1f15-9f81-cd13a4dbb871` |
| job_id / run_ids | 596114586206524 / 445061007036294, 260119777260260 |
| executor-hours before | 0.007445833 (baseline app `app-20260715202529-0011`; parity run app `app-20261111040114-0002`) |
| DBU after | 445061007036294: PENDING, 260119777260260: PENDING (billing statement `01f1dd85-6508-1205-b850-640cc561bfbd`; different unit from executor-hours) |
| status | RED |

## Retirement note
- The cron entry is commented out in `etl/crontab`; the last baseline History Server app is from 2026-07-15.
- Readers checked with `git grep docs_folder_legacy_report` and by searching for the lake path `documents/docs_folder_legacy_report`. Only inventory, metadata and tests mention the job (`etl/spark/jobs.txt`, `classification.yaml`, `k8s/`, `tests/`, `demos/app/complexity`). No SQL, job or service reads its output.
- Recommendation: **retire**. Its Databricks job has no schedule (it stays paused) and is kept only as parity evidence.
- RED: `FOLDER.PARENT_FOLDER_ID` is an output column, but neither `documents__folder` nor `documents__stg_folder` (0 rows) has a parent column, so it is NULL on both sides.
