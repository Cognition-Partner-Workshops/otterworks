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
# crosscheck rerun after the plan_code fix: run1 821791725568055, run2 49614676889700
```

## Parity
1. Export each `inputs.sql` SELECT to `billing/<TABLE>/<yyyymmdd>.psv`, `make sfx-spark-up SFX_SPARK_LANDING=<dir>`, `make sfx-spark-run JOB=billing_revenue_by_plan SFX_SPARK_LANDING=<dir>`; History Server: `curl localhost:18080/api/v1/applications/<app>`.
2. Load `etl/spark/.data/lake/billing/billing_revenue_by_plan` into `cpw.dbx_d1111_parity.billing__spark_billing_revenue_by_plan__spark_before`.
3. Run each statement of `parity.sql` (count + order-independent hash, EXCEPT ALL both ways); after run2 re-run the count-hash statement with `step=idempotence`.

Inputs (round one, trim() plan_code): INVOICE_LINE 4434 rows hash 01f1dd84-a6c7-154f-b12d-5c9fb86ad217; PLAN_CATALOG 40 rows hash 01f1dd84-a75b-11ec-b1e8-2ed8197fe234; local app app-20261111040253-0001.

Crosscheck fix: SUBSCRIPTION.PLAN_CODE and PLAN_CATALOG.PLAN_CODE are NOT CASESPECIFIC (warehouse/teradata/ddl/billing/00_tables.sql),
so Teradata's `s.PLAN_CODE=p.PLAN_CODE` (warehouse/teradata/procedures/monthly_invoice.sql) ignores case and trailing pad. Live codes include
`pro`, `Pro `, `team`: trim() matched 425/500 subscriptions and 2025/2084 'Monthly subscription' lines, upper(rtrim()) matches 500/500 and 2084/2084
(01f1dd8a-b57b-1f98-bd30-baf6009dd014, 01f1dd8a-b66a-1064-a11a-765e01bf11a0). billing_churn_score already used upper(rtrim()).
- Inputs after fix: INVOICE_LINE 4434 rows hash 2545716120304891311484, PLAN_CATALOG 40 rows hash 24112230574518220800, live (01f1dd8b-33d5-10ae-90ff-d40f97a6aace, 01f1dd8b-34b2-1452-aca0-972c19d3b2bd) = Spark-side landing read.
- Local Spark rerun (History Server): app-20261111044913-0000 (7071 ms, 2 executors, 4 stages, 0 failed tasks, 0 memory/disk spill); before table reloaded (01f1dd8b-5f40-13db-828c-6378a039c731).
- First failing comparison (corrected before vs round-one after): 40 = 40 rows, hash 23769761782253134664 vs 24170678708943300582; plan 1 revenue 2523.00 vs 1305.00, plan 2 6083.00 vs 4740.00 (01f1dd8b-601b-1b1a-b01e-213d83ecb430, 01f1dd8b-60a6-1809-bc4f-3b0d2ef252d7, 01f1dd8b-6123-1173-afa7-7f5a14ac86a3).
- Corrected: run 821791725568055, 40 = 40 rows, hash 23769761782253134664 both sides, EXCEPT ALL 0/0 (01f1dd8b-67ee-184e-973f-db1847be3042, 01f1dd8b-688b-1d8a-89f5-0c1a0c76a193, 01f1dd8b-68e1-1218-97c4-203e7b089aff).
- Idempotence: run 49614676889700, same count/hash; CREATE OR REPLACE numOutputRows 40 in versions 2 and 3 (01f1dd8b-6f7a-153d-ab11-62f8df5d98a9, 01f1dd8b-700d-1b5b-831e-eab248fdcb45).

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
| `billing_revenue_by_plan` | `etl/spark/jobs/py/billing_revenue_by_plan.py` | `cpw.dbx_d1111_after.billing__spark_billing_revenue_by_plan` | INVOICE_LINE.PLAN_ID unresolved in billing__invoice_line (and stg); corrected: PLAN_ID resolved for 'Monthly subscription' lines via invoice_hdr.subscription_id -> subscription.plan_code -> plan_catalog (warehouse/teradata/procedures/monthly_invoice.sql) (`01f1dd84-6bfe-1b98-99de-a0fed589081a`) ; crosscheck: trim() plan_code join left 75/500 subscriptions unmapped, corrected before vs old after hash 23769761782253134664 vs 24170678708943300582 (`01f1dd8b-601b-1b1a-b01e-213d83ecb430`) | 40 = 40 rows, hash 23769761782253134664 both sides, EXCEPT ALL 0/0 (`01f1dd8b-67ee-184e-973f-db1847be3042`) | run 49614676889700: 40 rows, same hash; CREATE OR REPLACE numOutputRows 40 (`01f1dd8b-6f7a-153d-ab11-62f8df5d98a9`, `01f1dd8b-700d-1b5b-831e-eab248fdcb45`) | 697530729305392 / 898103829480515, 1057735043935400, 821791725568055, 49614676889700 | 0.001860556 (app-20261110202335-0001) | PENDING | **green** |

