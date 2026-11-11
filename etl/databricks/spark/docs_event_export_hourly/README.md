<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# docs_event_export_hourly -> Databricks SQL (serverless)

Source: `etl/spark/jobs/py/docs_event_export_hourly.py` (cron `18 * * * *`, 10,000 bucket directories).
Target: `cpw.dbx_d1111_after.documents__spark_docs_event_export_hourly` (Delta), job `dbx-d1111-spark-docs_event_export_hourly` (job_id 274170347871647, no schedule).
Ordering: this job is upstream of `dbx-d1111-spark-lake_compaction_documents`; export must complete before compaction runs.

Files: `docs_event_export_hourly.sql` (sql_task), `job.json` (Jobs API 2.1 settings; `${DATABRICKS_WAREHOUSE_ID}` is substituted at deploy), `inputs.sql`, `parity.sql`.

## Commands
```sh
# deploy: upload the .sql to /Workspace/Shared/dbx-d1111-spark/docs_event_export_hourly/ (workspace/import RAW), then jobs/create or jobs/reset with job.json
# run:    POST /api/2.1/jobs/run-now {"job_id": 274170347871647}
# parity: execute each statement in parity.sql on the warehouse (Statement Execution API)
```
Before result: `inputs.sql` exported to `documents/DOCUMENT/20261111.psv`, original job run locally (`make sfx-spark-run JOB=docs_event_export_hourly`), parquet loaded into `cpw.dbx_d1111_parity.documents__spark_docs_event_export_hourly__spark_before`.

## Standard
- Adaptive execution: serverless SQL warehouse (AQE always on). Removed `--executor-memory 1400m --executor-cores 2 --total-executor-cores 4`, `spark.sql.shuffle.partitions=8` and `repartition(8, EXPORT_BUCKET)`.
- Retries: task max_retries=2, min_retry_interval_millis=60000, retry_on_timeout=false, timeout_seconds=1800.
- Partition sizing: no `partitionBy(EXPORT_BUCKET)` (10,000 tiny directories/files); EXPORT_BUCKET is a column and Delta sizes the files (1 file for 450 rows). No CLUSTER BY: the only downstream reader (compaction) reads the whole table.
- Idempotent writes: `CREATE OR REPLACE TABLE ... AS` (the source overwrote the whole export each hour).
- Preserved: `pmod(DOCUMENT_ID, DOCUMENT_ID*0 + 10000)` (BIGINT, NULL for NULL id), all DOCUMENT columns and types.

## Board row
| source | target | first failure | corrected parity | idempotence | job / runs | executor-hours before | DBU after | status |
|---|---|---|---|---|---|---|---|---|
| docs_event_export_hourly.py | documents__spark_docs_event_export_hourly | adapter kept CHAR(12) status_cd padding: hash 253226484014410365799 vs 262073977905134504305 (01f1dd84-bdcd-1a99-ae94-a303163cdc3e) | 450/450 rows, hash 262073977905134504305, EXCEPT ALL 0/0 (01f1dd84-b99a-1c37-bcbf-eefd4f6310f1, 01f1dd84-ba34-1fb9-8725-e2d791aac0b5) | run2 unchanged; numOutputRows 450/450 (01f1dd84-e534-1d91-a3d3-a496d97786fb, 01f1dd84-e5ba-1cb1-b7ee-44f9e16ea14e, 01f1dd84-e63a-1254-8594-6d896d14353a) | 274170347871647 / 969908575640356, 800715699101340 | 0.013149444 (app-20261110202641-0018) | PENDING | green |

Input proof: live adapter 450 rows, hash 251670673998716658352 (01f1dd84-7a8b-1d9c-9c67-a52b14bccace) = same count and hash computed by Spark over the landing PSV.
Local before run: History Server app-20261111035936-0000, 6.3 s, 2 executors / 4 cores, 0 failed tasks, 0 spill, 450 records in/out, 400 parquet files.

## Query history
```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status FROM system.query.history WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=docs_event_export_hourly */%' ORDER BY start_time
```
```sql
SELECT usage_metadata.job_run_id, sku_name, sum(usage_quantity) AS dbus FROM system.billing.usage
WHERE usage_metadata.job_id = '274170347871647' GROUP BY 1, 2
```
