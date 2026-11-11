<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# billing_usage_append_daily -> Databricks SQL (serverless)

Source `etl/spark/jobs/py/billing_usage_append_daily.py` -> target `cpw.dbx_d1111_after.billing__spark_billing_usage_append_daily`. Status **red**.

Files: `inputs.sql` (live -> landing adapter, one SELECT per landing table), `job.sql` (migrated logic, `sql_task` file on the serverless warehouse), `job.json` (Jobs API 2.1 settings), `parity.sql`.

## Run
```sh
# upload + create (no schedule) + run twice; WAREHOUSE_ID is substituted into job.json at create time
databricks workspace import /Workspace/Shared/dbx-d1111-spark/billing_usage_append_daily/job.sql --file job.sql --format AUTO --overwrite
databricks jobs create --json @job.json          # job_id 159267749013173
databricks jobs run-now 159267749013173             # run1 1035495213185722
databricks jobs run-now 159267749013173             # run2 916699487965450
```

## Parity
1. Export each `inputs.sql` SELECT to `billing/<TABLE>/<yyyymmdd>.psv`, `make sfx-spark-up SFX_SPARK_LANDING=<dir>`, `make sfx-spark-run JOB=billing_usage_append_daily SFX_SPARK_LANDING=<dir>`; History Server: `curl localhost:18080/api/v1/applications/<app>`.
2. Load `etl/spark/.data/lake/billing/billing_usage_append_daily` into `cpw.dbx_d1111_parity.billing__spark_billing_usage_append_daily__spark_before`.
3. Run each statement of `parity.sql` (count + order-independent hash, EXCEPT ALL both ways); after run2 re-run the count-hash statement with `step=idempotence`.

Inputs: USAGE_DAILY 2250 rows hash 01f1dd84-a817-1be8-9ac3-6cf2da44bb66; equal to Spark-side count/hash.
Local Spark run (History Server): app-20261111040306-0002 run1 / app-20261111040320-0003 run2 (8180/8208 ms, 2 executors, 0 failed tasks, 0 spill).

Crosscheck: job.sql now starts with the `/* run=dbx-d1111 act=spark ... */` prefix (the leading `-- run_token` comment had made system.query.history statement_text miss the prefix). Same SQL otherwise; run3 875418758524811, 01f1dd8b-98c1-19de-9f80-843322f65ad1: 917 rows, hash 531001693408086517936 unchanged; MERGE inserted 0 updated 0 (01f1dd8b-994f-18f7-98ff-b12636e37ecc).

## Query history
```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status FROM system.query.history WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=billing_usage_append_daily */%' ORDER BY start_time
```
Billing: `SELECT * FROM system.billing.usage WHERE usage_metadata.job_id = '159267749013173'` (lags hours; report PENDING, never zero).

## Standard settings
- Adaptive execution: serverless SQL warehouse (AQE on by default); no executor memory/cores, shuffle partitions, repartition/coalesce.
- Retries: task `max_retries=2`, `min_retry_interval_millis=60000`, `retry_on_timeout=false`, `timeout_seconds=1800`; no schedule.
- Partition sizing: Delta target, no fixed file count, no CLUSTER BY/partitioning (no downstream contract needs it).
- Idempotent writes: MERGE on USAGE_ID of the latest USAGE_DATE slice (the Spark append duplicated it on rerun).
- Tags `run_token=dbx-d1111`, `expires=2026-11-24`, `act=spark` on job; table COMMENT + TBLPROPERTIES.

## Board row
| job | source | target | first failure (statement_id) | corrected parity (statement_id) | idempotence (statement_ids) | job_id / run_ids | executor-hours before (baseline app) | DBU after | status |
|---|---|---|---|---|---|---|---|---|---|
| `billing_usage_append_daily` | `etl/spark/jobs/py/billing_usage_append_daily.py` | `cpw.dbx_d1111_after.billing__spark_billing_usage_append_daily` | USAGE_DAILY.AMOUNT unresolved in billing__usage_daily (and stg 01f1dd85-2d6f-1e38-b069-c2f5774d9b60). Idempotence first failure: original Spark rerun duplicates the slice 917 -> 1834 rows (lake and JDBC, 917 distinct USAGE_ID) 01f1dd85-147a-1244-8f8b-5fdae63c0b49 (`01f1dd85-2d37-1ec7-8030-2dd1b0238834`) | 917 = 917 rows, hash 531001693408086517936 both sides, EXCEPT ALL 0/0 (AMOUNT NULL both sides) (`01f1dd85-12c3-18f5-9551-c447b0e046e0`) | Spark original FAILS (917 -> 1834, 01f1dd85-147a-1244-8f8b-5fdae63c0b49); migrated MERGE run2: 917 rows same hash, numSourceRows 917, inserted 0, updated 0 (`01f1dd85-147a-1244-8f8b-5fdae63c0b49`, `01f1dd85-2b23-186a-8720-c07d10667794`, `01f1dd85-306d-11cc-9d29-c888eee0a533`) | 159267749013173 / 1035495213185722, 916699487965450 | 0.003107778 (app-20261110202352-0003) | PENDING | **red** |
Red reason: USAGE_DAILY.AMOUNT has no live equivalent (billing__usage_daily, billing__stg_usage_daily); output AMOUNT would be NULL. Logic, parity on remaining columns and idempotent MERGE are proven
