<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# billing_revenue_by_plan -> Databricks SQL (serverless)

Source `etl/spark/jobs/py/billing_revenue_by_plan.py` -> target `cpw.dbx_d1111_after.billing__spark_billing_revenue_by_plan`. Status **green**.

Files: `inputs.sql` (live -> landing adapter, one SELECT per landing table), `job.sql` (migrated logic, `sql_task` file on the serverless warehouse), `job.json` (Jobs API 2.1 settings), `parity.sql`.

## Run
```sh
# upload + create (no schedule) + run twice; WAREHOUSE_ID is substituted into job.json at create time
databricks workspace import /Workspace/Shared/dbx-d1111-spark/billing_revenue_by_plan/job.sql --file job.sql --format AUTO --overwrite
databricks jobs create --json @job.json          # job_id 697530729305392
databricks jobs run-now 697530729305392             # run1 898103829480515
databricks jobs run-now 697530729305392             # run2 1057735043935400
```

## Parity
1. Export each `inputs.sql` SELECT to `billing/<TABLE>/<yyyymmdd>.psv`, `make sfx-spark-up SFX_SPARK_LANDING=<dir>`, `make sfx-spark-run JOB=billing_revenue_by_plan SFX_SPARK_LANDING=<dir>`; History Server: `curl localhost:18080/api/v1/applications/<app>`.
2. Load `etl/spark/.data/lake/billing/billing_revenue_by_plan` into `cpw.dbx_d1111_parity.billing__spark_billing_revenue_by_plan__spark_before`.
3. Run each statement of `parity.sql` (count + order-independent hash, EXCEPT ALL both ways); after run2 re-run the count-hash statement with `step=idempotence`.

Inputs: INVOICE_LINE 4434 rows hash 01f1dd84-a6c7-154f-b12d-5c9fb86ad217; PLAN_CATALOG 40 rows hash 01f1dd84-a75b-11ec-b1e8-2ed8197fe234; equal to Spark-side counts/hashes.
Local Spark run (History Server): app-20261111040253-0001 (6086 ms, 2 executors, 0 failed tasks, 0 spill).

## Query history
```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status FROM system.query.history WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=billing_revenue_by_plan */%' ORDER BY start_time
```
Billing: `SELECT * FROM system.billing.usage WHERE usage_metadata.job_id = '697530729305392'` (lags hours; report PENDING, never zero).

## Standard settings
- Adaptive execution: serverless SQL warehouse (AQE on by default); no executor memory/cores, shuffle partitions, repartition/coalesce.
- Retries: task `max_retries=2`, `min_retry_interval_millis=60000`, `retry_on_timeout=false`, `timeout_seconds=1800`; no schedule.
- Partition sizing: Delta target, no fixed file count, no CLUSTER BY/partitioning (no downstream contract needs it).
- Idempotent writes: CREATE OR REPLACE TABLE ... AS (Spark mode=overwrite).
- Tags `run_token=dbx-d1111`, `expires=2026-11-24`, `act=spark` on job; table COMMENT + TBLPROPERTIES.

## Board row
| job | source | target | first failure (statement_id) | corrected parity (statement_id) | idempotence (statement_ids) | job_id / run_ids | executor-hours before (baseline app) | DBU after | status |
|---|---|---|---|---|---|---|---|---|---|
| `billing_revenue_by_plan` | `etl/spark/jobs/py/billing_revenue_by_plan.py` | `cpw.dbx_d1111_after.billing__spark_billing_revenue_by_plan` | INVOICE_LINE.PLAN_ID unresolved in billing__invoice_line (and stg); corrected: PLAN_ID resolved for 'Monthly subscription' lines via invoice_hdr.subscription_id -> subscription.plan_code -> plan_catalog (warehouse/teradata/procedures/monthly_invoice.sql) (`01f1dd84-6bfe-1b98-99de-a0fed589081a`) | 40 = 40 rows, hash 24170678708943300582 both sides, EXCEPT ALL 0/0 (`01f1dd85-1114-1f55-8cec-06cd9222f520`) | run2: 40 rows, same hash; CREATE OR REPLACE numOutputRows 40 both versions (`01f1dd85-2a80-1499-94e2-f33bf45fd291`, `01f1dd85-2f7a-1ed9-891e-e32aa9fb8f5b`) | 697530729305392 / 898103829480515, 1057735043935400 | 0.001860556 (app-20261110202335-0001) | PENDING | **green** |

