<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# lake_compaction_documents -> OPTIMIZE + Databricks SQL (serverless)

Source: `etl/spark/scala/src/main/scala/sfx/LakeCompactionDocuments.scala` (cron `19 2 * * *`): reads the docs_event_export_hourly parquet, `coalesce(4)`, rewrites it.
Target: `cpw.dbx_d1111_after.documents__spark_lake_compaction_documents` (Delta), job `dbx-d1111-spark-lake_compaction_documents` (job_id 258461135155454, no schedule).
Tasks: `optimize_export` (`OPTIMIZE` on the export table: the compaction itself) -> `compact` (CTAS of the compacted dataset, the source's output contract).
Ordering: runs only after `dbx-d1111-spark-docs_event_export_hourly` completed (export -> compaction); the combined orchestration must keep this dependency.

Files: `optimize_export.sql`, `lake_compaction_documents.sql`, `job.json`, `inputs.sql`, `parity.sql`.

## Commands
```sh
# deploy: upload both .sql files to /Workspace/Shared/dbx-d1111-spark/lake_compaction_documents/, jobs/create or jobs/reset with job.json
# run:    POST /api/2.1/jobs/run-now {"job_id": 258461135155454}   (after the export job)
# parity: execute each statement in parity.sql
```

## Standard
- Adaptive execution: serverless SQL (AQE on). Removed `--executor-memory 1500m --executor-cores 2 --total-executor-cores 4`, `spark.sql.files.maxPartitionBytes=16777216`, `coalesce(4)`.
- Retries: both tasks max_retries=2, min_retry_interval_millis=60000, retry_on_timeout=false, timeout_seconds=1800.
- Partition sizing: Delta, no fixed file count; small files are handled by OPTIMIZE, so the hourly export no longer creates a compaction problem.
- Idempotent writes: OPTIMIZE is idempotent; `CREATE OR REPLACE TABLE ... AS`.
- Preserved: column order, EXPORT_BUCKET as INT (parquet partition inference type, last column).

## Board row
| source | target | first failure | corrected parity | idempotence | job / runs | executor-hours before | DBU after | status |
|---|---|---|---|---|---|---|---|---|
| LakeCompactionDocuments.scala | documents__spark_lake_compaction_documents | none observed (input is the export table; inherits the export adapter fix) | 450/450 rows, hash 262073977905134504305, EXCEPT ALL 0/0 (01f1dd84-bbb9-1e3f-80d0-ea17fb50175f, 01f1dd84-bc76-1db4-8a78-776dfc500d91) | run2 unchanged; numOutputRows 450/450 (01f1dd84-e740-1680-b1ce-b613745111d1, 01f1dd84-e7e2-1973-9630-ba31484735f3, 01f1dd84-e84e-1e5b-b18c-c5a6943693e0) | 258461135155454 / 1055357238185615, 382673924698076 | 0.012373611 (app-20261110202709-0019) | PENDING | green |

Local before run: History Server app-20261111035947-0001, 6.4 s, 2 executors / 4 cores, 0 failed tasks, 0 spill, 450 records in/out, 4 output files.

## Query history
```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status FROM system.query.history WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=lake_compaction_documents */%' ORDER BY start_time
```
```sql
SELECT usage_metadata.job_run_id, sku_name, sum(usage_quantity) AS dbus FROM system.billing.usage
WHERE usage_metadata.job_id = '258461135155454' GROUP BY 1, 2
```
