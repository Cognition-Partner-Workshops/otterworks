<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# file_object_binary_extract -> stays on Spark (common Spark template)

Source: `etl/spark/jobs/py/file_object_binary_extract.py` (cron `26 3 * * *`). This is the one job kept on Spark.
No Databricks job is created.

## Why it stays (evidence)
- It reads `binaryFile` over the self-run blob store `/opt/landing/documents/FILE_OBJECT_BLOBS/*` (8 blobs, 2,182,861 bytes locally) and joins the extracted content to FILE_OBJECT on STORAGE_KEY.
- Live `cpw.dbx_d1111_before.documents__file_object` has no STORAGE_KEY or CHECKSUM column; its object_key addresses another store: 2000 rows, 0 keys of the form `documents/FILE_OBJECT_BLOBS/<name>` (01f1dd85-3dd2-115a-b3b0-a64247cb4a23). On live data the join would return 0 rows. This is the first failing result.
- `SHOW VOLUMES IN cpw.dbx_d1111_before` returns no volume (01f1dd85-3e48-1875-81fd-6e5adba8698a); creating a volume, external location or other storage is not allowed, so a serverless job cannot read the blobs.

## Template
`etl/spark/submit/file_object_binary_extract.sh` now calls `etl/spark/template/submit.sh`, which applies `etl/spark/template/spark-defaults.template.conf`:
- Adaptive execution: AQE, coalescePartitions, skewJoin on; fixed `spark.sql.shuffle.partitions=6` removed.
- Retries: `spark.task.maxFailures=4`, `spark.stage.maxConsecutiveAttempts=4`, and the wrapper retries the whole application 2 times after 60 s.
- Partition sizing: `spark.sql.files.maxPartitionBytes=128MiB`, `advisoryPartitionSizeInBytes=64MiB`.
- Idempotent writes: the job writes under `LAKE_DIR=<lake>/.staging/<job>/<run>`; on success the output becomes `<lake>/.versions/<job>/<run>` and `<lake>/documents/file_object_binary_extract` (relative symlink) is switched with one atomic rename; failed attempts publish nothing. `spark.sql.sources.partitionOverwriteMode=dynamic` for partitioned outputs.
- Executor sizing (768m, 1 core, 3 executors) is kept in the job's submit script, matching its k8s manifest.

## Evidence (local Spark, History Server)
| run | app id | duration | executors/cores | failed tasks | spill | AQE | rows | output hash |
|---|---|---|---|---|---|---|---|---|
| before (original submit) | app-20261111040159-0002 | 6.2 s | 3/3 | 0 | 0 | unset (default) | 2000 | 1158281207022607207777 |
| template run 1 | app-20261111040450-0006 | 6.6 s | 3/3 | 0 | 0 | true | 2000 | 1158281207022607207777 |
| template run 2 | app-20261111040502-0007 | 6.0 s | 3/3 | 0 | 0 | true | 2000 | 1158281207022607207777 |
Baseline executor-hours: 0.008545 (app-20261110202856-0026, etl/spark/history/baseline.json).

## Commands
```sh
make sfx-spark-up && make sfx-spark-run JOB=file_object_binary_extract   # twice; output is swapped, never duplicated
curl -s http://localhost:18080/api/v1/applications
```

## Board row
| source | target | first failure | corrected parity | idempotence | job / runs | executor-hours before | DBU after | status |
|---|---|---|---|---|---|---|---|---|
| file_object_binary_extract.py | Spark common template (kept) | live file_object lacks STORAGE_KEY/CHECKSUM, 0/2000 joinable keys; no UC volume (01f1dd85-3dd2-115a-b3b0-a64247cb4a23, 01f1dd85-3e48-1875-81fd-6e5adba8698a) | n/a on Databricks; template = before: 2000 rows, same hash | template run1 = run2 | none (stays on Spark) | 0.008545 (app-20261110202856-0026) | n/a | red (kept on Spark by design) |

## Query history
```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status FROM system.query.history WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=file_object_binary_extract */%' ORDER BY start_time
```
