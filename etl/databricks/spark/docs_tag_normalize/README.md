<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# docs_tag_normalize -> Databricks serverless PySpark

Source: `etl/spark/jobs/py/docs_tag_normalize.py` (Python regex UDF, logic-heavy -> PySpark serverless job).
Target: `cpw.dbx_d1111_after.documents__spark_docs_tag_normalize` (Delta, CREATE OR REPLACE TABLE AS SELECT).

| File | Purpose |
| --- | --- |
| docs_tag_normalize.py | Migrated job: reads the inputs.sql adapter, applies the original `normalize` logic unchanged as a Python UDF, writes the target. |
| inputs.sql | Live adapter: `documents__doc_tag` (tag_id, document_id, tag_name) -> landing DOC_TAG (DOC_TAG_ID, DOCUMENT_ID, TAG). |
| job.json | Jobs API 2.1 settings (serverless `spark_python_task` + `environments`, no cluster, no schedule). |
| parity.sql | Count + order-independent hash, EXCEPT ALL both ways, Delta history for idempotence. |
| test_docs_tag_normalize.py | Unit test: migrated `normalize_tag` equals the original UDF on edge cases (None, Unicode whitespace, case folding). |

## Commands

```sh
# unit test (Spark 3.5.3 image; pyspark import only)
docker run --rm -v $PWD:/r:ro -w /r -e PYTHONPATH=/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip \
  mirror.gcr.io/library/spark:3.5.3-scala2.12-java17-python3-ubuntu \
  python3 -m unittest etl/databricks/spark/docs_tag_normalize/test_docs_tag_normalize.py
# before result: export inputs.sql to <landing>/documents/DOC_TAG/20241109.psv (header, '|'), then
make sfx-spark-up SFX_SPARK_LANDING=<abs landing> ROWS_PER_TABLE=1000   # replace the generated DOC_TAG file with the export
make sfx-spark-run JOB=docs_tag_normalize SFX_SPARK_LANDING=<abs landing>
curl -s localhost:18080/api/v1/applications/<app id>/allexecutors
# deploy: import docs_tag_normalize.py and inputs.sql to /Workspace/Shared/dbx-d1111-spark/docs_tag_normalize/,
# POST /api/2.1/jobs/create with job.json, then POST /api/2.1/jobs/run-now {"job_id": <id>} (twice for idempotence)
# parity: send each block of parity.sql via POST /api/2.0/sql/statements on the serverless warehouse
```

## Standard settings

- Adaptive execution: serverless AQE (always on). Reading `spark.sql.adaptive.enabled` at runtime returned `AnalysisException` (config not readable on serverless; logged as `unavailable` in both runs). Removed `--executor-memory 768m --executor-cores 2 --total-executor-cores 4` and `spark.sql.shuffle.partitions=9`; no repartition/coalesce.
- Retries: task `max_retries=2`, `min_retry_interval_millis=60000`, `retry_on_timeout=false`, `timeout_seconds=1800`.
- Partition sizing: unpartitioned Delta table, no fixed file count (1 file for 1000 rows); no downstream contract needs CLUSTER BY.
- Idempotent write: `CREATE OR REPLACE TABLE ... AS SELECT` (the original overwrote its parquet directory), so a rerun replaces, never appends.
- Behaviour preserved: the original `re.sub(r"\s+", "-", (tag or "").strip().lower())` runs as the same Python function (Python Unicode `\s`/`strip` semantics differ from Spark SQL `trim`/Java regex, so it is not rewritten to SQL); NULL TAG -> '' as in the original; column order and BIGINT/STRING types kept.

## Evidence

- Input proof: local Spark landing read 1000 rows, hash 587431028310658432658 = live adapter 1000 rows, hash 587431028310658432658 (statement 01f1dd84-9151-15aa-8d8a-5705846f4a68).
- Before: local History Server app `app-20261111040047-0000` (4182 ms, 2 executors x 2 cores, 0 failed tasks, 0 memory/disk spill, 1000 records in/out) loaded to `cpw.dbx_d1111_parity.documents__spark_docs_tag_normalize__spark_before` (check 01f1dd84-94da-11c6-8429-557a58c58338).
- First failure: job run 759583532929649 (task 490714203646892 + 2 retries) INTERNAL_ERROR, ParseException on CTAS with a typed column list; run 257297868817904 hit the same and was cancelled. Corrected: column types moved to CASTs in the SELECT.
- Corrected parity (run 602474958615587): before 1000 / 586596083625798495746 = after 1000 / 586596083625798495746 (01f1dd86-4282-1b69-b771-cc71e07a3471); EXCEPT ALL 0 rows each way (01f1dd86-433a-1e32-b46f-ed4c93da4f71, 01f1dd86-4395-1855-8b6c-eaa343df60b1).
- Idempotence (run 519768950748371): 1000 / 586596083625798495746 (01f1dd86-692a-16fe-b4af-d3c91c3583c5), EXCEPT ALL 0/0 (01f1dd86-69b8-106f-812b-d06351f2434a, 01f1dd86-6a0c-1a36-acae-1f46ba906627); Delta history v0 and v1 both CREATE OR REPLACE TABLE AS SELECT numOutputRows=1000 numFiles=1 numOutputBytes=3686 (01f1dd86-6a84-1f05-bafa-5065b8437319).

## Query history

```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status FROM system.query.history WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=docs_tag_normalize */%' ORDER BY start_time
```

## Board row

| source | target | first failure | corrected parity | idempotence | job / runs | executor-hours before | DBU after | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| etl/spark/jobs/py/docs_tag_normalize.py | cpw.dbx_d1111_after.documents__spark_docs_tag_normalize | run 759583532929649 ParseException (CTAS typed column list) | 1000 rows, hash equal, EXCEPT ALL 0/0 (01f1dd86-4282-1b69-b771-cc71e07a3471) | unchanged (01f1dd86-692a-16fe-b4af-d3c91c3583c5, 01f1dd86-6a84-1f05-bafa-5065b8437319) | 885937093057247 / 602474958615587, 519768950748371 | 0.001232222 (app-20261110202558-0014) | see PR | green |
