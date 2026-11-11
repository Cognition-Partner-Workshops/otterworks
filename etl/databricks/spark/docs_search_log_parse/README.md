<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# docs_search_log_parse -> Databricks serverless PySpark (RED: no live input)

Source: `etl/spark/jobs/py/docs_search_log_parse.py` (Python UDF, logic-heavy -> PySpark serverless job).
Planned target: `cpw.dbx_d1111_after.documents__spark_docs_search_log_parse` (Delta, CREATE OR REPLACE TABLE AS SELECT). Not created: there is no defensible live input.

| File | Purpose |
| --- | --- |
| docs_search_log_parse.py | Migrated job (original UDF logic unchanged, idempotent CTAS write). |
| inputs.sql | Landing SEARCH_INDEX_LOG mapping notes and the gap check that is the first failing result. |
| job.json | Jobs API 2.1 settings that would be used (serverless, no schedule). Not deployed. |
| parity.sql | Comparison statements to run once a live input exists. |
| test_docs_search_log_parse.py | Unit test: migrated UDF equals the original on edge cases (values and raised errors). |

## Commands

```sh
docker run --rm -v $PWD:/r:ro -w /r -e PYTHONPATH=/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip \
  mirror.gcr.io/library/spark:3.5.3-scala2.12-java17-python3-ubuntu \
  python3 -m unittest etl/databricks/spark/docs_search_log_parse/test_docs_search_log_parse.py
# gap check: send inputs.sql via POST /api/2.0/sql/statements on the serverless warehouse
```

## First failing result (statement 01f1dd84-5580-1e45-bb6d-3573b49ca8ed)

`documents__search_index_log` has 0 rows; `documents__stg_search_index_log` has 2000 rows, but neither table (nor the Teradata DDL in warehouse/teradata/ddl/documents/00_tables.sql) has a RAW_LINE column (found 0). RAW_LINE is the only column the job parses (`action=(\w+)`), so the output column PARSED_ACTION cannot be produced from live data.

The job is RED. No data was fabricated, so no before result, Databricks job, run, parity or idempotence evidence exists.

## Standard settings (applied in the code and job.json)

- Adaptive execution: serverless AQE; removed `--executor-memory 1g --executor-cores 1 --total-executor-cores 2` and `spark.sql.shuffle.partitions=6`; no repartition/coalesce.
- Retries: task `max_retries=2`, `min_retry_interval_millis=60000`, `retry_on_timeout=false`, `timeout_seconds=1800`.
- Partition sizing: unpartitioned Delta, no fixed file count, no downstream contract needing CLUSTER BY.
- Idempotent write: `CREATE OR REPLACE TABLE ... AS SELECT` (the original overwrote its parquet directory).
- Behaviour preserved: the original UDF body runs unchanged as a Python UDF; column order and types kept.

## Query history

```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status FROM system.query.history WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=docs_search_log_parse */%' ORDER BY start_time
```

## Board row

| source | target | first failure | corrected parity | idempotence | job / runs | executor-hours before | DBU after | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| etl/spark/jobs/py/docs_search_log_parse.py | cpw.dbx_d1111_after.documents__spark_docs_search_log_parse (not created) | 01f1dd84-5580-1e45-bb6d-3573b49ca8ed | none | none | not deployed | 0.001591111 (app-20261110202540-0012) | n/a (no runs) | red |
