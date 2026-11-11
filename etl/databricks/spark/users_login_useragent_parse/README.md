<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# users_login_useragent_parse -> Databricks serverless PySpark (RED: no live input)

Source: `etl/spark/jobs/py/users_login_useragent_parse.py` (Python UDF, logic-heavy -> PySpark serverless job).
Planned target: `cpw.dbx_d1111_after.users__spark_users_login_useragent_parse` (Delta, CREATE OR REPLACE TABLE AS SELECT). Not created: there is no defensible live input.

| File | Purpose |
| --- | --- |
| users_login_useragent_parse.py | Migrated job (original UDF logic unchanged, idempotent CTAS write). |
| inputs.sql | Landing LOGIN_EVENT mapping notes and the gap check that is the first failing result. |
| job.json | Jobs API 2.1 settings that would be used (serverless, no schedule). Not deployed. |
| parity.sql | Comparison statements to run once a live input exists. |
| test_users_login_useragent_parse.py | Unit test: migrated UDF equals the original on edge cases (values and raised errors). |

## Commands

```sh
docker run --rm -v $PWD:/r:ro -w /r -e PYTHONPATH=/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip \
  mirror.gcr.io/library/spark:3.5.3-scala2.12-java17-python3-ubuntu \
  python3 -m unittest etl/databricks/spark/users_login_useragent_parse/test_users_login_useragent_parse.py
# gap check: send inputs.sql via POST /api/2.0/sql/statements on the serverless warehouse
```

## First failing result (statement 01f1dd84-562a-131d-91f6-ecd46eac92d1)

`users__login_event` (2000 rows) and `users__stg_login_event` (2000 rows) have login_id, user_id, login_ts, result_cd, client_type; none of USER_AGENT, IP_ADDRESS, RAW_LINE exists (found 0). client_type holds device categories (API/DESKTOP/MOBILE/WEB), not user-agent strings; mapping it would make every BROWSER 'Other' and is not an equivalent.

The job is RED. No data was fabricated, so no before result, Databricks job, run, parity or idempotence evidence exists.

## Standard settings (applied in the code and job.json)

- Adaptive execution: serverless AQE; removed `--executor-memory 850m --executor-cores 1 --num-executors 2` and `spark.python.worker.memory=128m`; no repartition/coalesce.
- Retries: task `max_retries=2`, `min_retry_interval_millis=60000`, `retry_on_timeout=false`, `timeout_seconds=1800`.
- Partition sizing: unpartitioned Delta, no fixed file count, no downstream contract needing CLUSTER BY.
- Idempotent write: `CREATE OR REPLACE TABLE ... AS SELECT` (the original overwrote its parquet directory).
- Behaviour preserved: the original UDF body runs unchanged as a Python UDF; column order and types kept.

## Query history

```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status FROM system.query.history WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=users_login_useragent_parse */%' ORDER BY start_time
```

## Board row

| source | target | first failure | corrected parity | idempotence | job / runs | executor-hours before | DBU after | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| etl/spark/jobs/py/users_login_useragent_parse.py | cpw.dbx_d1111_after.users__spark_users_login_useragent_parse (not created) | 01f1dd84-562a-131d-91f6-ecd46eac92d1 | none | none | not deployed | 0.005469167 (app-20261110202547-0013) | n/a (no runs) | red |
