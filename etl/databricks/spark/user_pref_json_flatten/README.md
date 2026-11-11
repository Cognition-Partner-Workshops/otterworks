<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# user_pref_json_flatten -> Databricks serverless PySpark (RED: no live input)

Source: `etl/spark/jobs/py/user_pref_json_flatten.py` (Python UDF, logic-heavy -> PySpark serverless job).
Planned target: `cpw.dbx_d1111_after.users__spark_user_pref_json_flatten` (Delta, CREATE OR REPLACE TABLE AS SELECT). Not created: there is no defensible live input.

| File | Purpose |
| --- | --- |
| user_pref_json_flatten.py | Migrated job (original UDF logic unchanged, idempotent CTAS write). |
| inputs.sql | Landing USER_PREF mapping notes and the gap check that is the first failing result. |
| job.json | Jobs API 2.1 settings that would be used (serverless, no schedule). Not deployed. |
| parity.sql | Comparison statements to run once a live input exists. |
| test_user_pref_json_flatten.py | Unit test: migrated UDF equals the original on edge cases (values and raised errors). |

## Commands

```sh
docker run --rm -v $PWD:/r:ro -w /r -e PYTHONPATH=/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip \
  mirror.gcr.io/library/spark:3.5.3-scala2.12-java17-python3-ubuntu \
  python3 -m unittest etl/databricks/spark/user_pref_json_flatten/test_user_pref_json_flatten.py
# gap check: send inputs.sql via POST /api/2.0/sql/statements on the serverless warehouse
```

## First failing result (statement 01f1dd84-56e1-10b0-b78f-0f95688a9279)

`users__user_pref` has 0 rows; `users__stg_user_pref` has 200 normalized name/value rows (pref_name in editor_theme, notification_digest, review_reminders) and no PREF_JSON column (found 0). The job extracts keys theme, notifications, locale from PREF_JSON; none exists live, and assembling JSON from pref_name/pref_value would be derived data with no basis in etl/ or warehouse/ DDL.

The job is RED. No data was fabricated, so no before result, Databricks job, run, parity or idempotence evidence exists.

## Standard settings (applied in the code and job.json)

- Adaptive execution: serverless AQE; removed `--executor-memory 850m --executor-cores 2 --total-executor-cores 4` and `spark.sql.shuffle.partitions=10`; no repartition/coalesce.
- Retries: task `max_retries=2`, `min_retry_interval_millis=60000`, `retry_on_timeout=false`, `timeout_seconds=1800`.
- Partition sizing: unpartitioned Delta, no fixed file count, no downstream contract needing CLUSTER BY.
- Idempotent write: `CREATE OR REPLACE TABLE ... AS SELECT` (the original overwrote its parquet directory).
- Behaviour preserved: the original UDF body runs unchanged as a Python UDF; column order and types kept.

## Query history

```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status FROM system.query.history WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=user_pref_json_flatten */%' ORDER BY start_time
```

## Board row

| source | target | first failure | corrected parity | idempotence | job / runs | executor-hours before | DBU after | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| etl/spark/jobs/py/user_pref_json_flatten.py | cpw.dbx_d1111_after.users__spark_user_pref_json_flatten (not created) | 01f1dd84-56e1-10b0-b78f-0f95688a9279 | none | none | not deployed | 0.001498611 (app-20261110202922-0028) | n/a (no runs) | red |
