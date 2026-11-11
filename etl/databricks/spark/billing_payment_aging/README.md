<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# billing_payment_aging -> Databricks SQL (serverless)

Source `etl/spark/jobs/py/billing_payment_aging.py` -> target `cpw.dbx_d1111_after.billing__spark_billing_payment_aging`. Status **red**.

Files: `inputs.sql` (live -> landing adapter, one SELECT per landing table), `job.sql` (migrated logic, `sql_task` file on the serverless warehouse), `job.json` (Jobs API 2.1 settings), `parity.sql`.

## Run
Not deployed: the job is RED (see board row). `job.sql` and `job.json` are the target once the missing source column exists.

## Parity
1. Export each `inputs.sql` SELECT to `billing/<TABLE>/<yyyymmdd>.psv`, `make sfx-spark-up SFX_SPARK_LANDING=<dir>`, `make sfx-spark-run JOB=billing_payment_aging SFX_SPARK_LANDING=<dir>`; History Server: `curl localhost:18080/api/v1/applications/<app>`.
2. Load `etl/spark/.data/lake/billing/billing_payment_aging` into `cpw.dbx_d1111_parity.billing__spark_billing_payment_aging__spark_before`.
3. Run each statement of `parity.sql` (count + order-independent hash, EXCEPT ALL both ways); after run2 re-run the count-hash statement with `step=idempotence`.

Inputs: not exported: required INVOICE_HDR.DUE_DATE missing.


## Query history
```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status FROM system.query.history WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=billing_payment_aging */%' ORDER BY start_time
```
Billing: `SELECT * FROM system.billing.usage WHERE usage_metadata.job_id = '<job_id>'` (lags hours; report PENDING, never zero).

## Standard settings
- Adaptive execution: serverless SQL warehouse (AQE on by default); no executor memory/cores, shuffle partitions, repartition/coalesce.
- Retries: task `max_retries=2`, `min_retry_interval_millis=60000`, `retry_on_timeout=false`, `timeout_seconds=1800`; no schedule.
- Partition sizing: Delta target, no fixed file count, no CLUSTER BY/partitioning (no downstream contract needs it).
- Idempotent writes: CREATE OR REPLACE TABLE ... AS (Spark mode=overwrite).
- Tags `run_token=dbx-d1111`, `expires=2026-11-24`, `act=spark` on job; table COMMENT + TBLPROPERTIES.

## Board row
| job | source | target | first failure (statement_id) | corrected parity (statement_id) | idempotence (statement_ids) | job_id / run_ids | executor-hours before (baseline app) | DBU after | status |
|---|---|---|---|---|---|---|---|---|---|
| `billing_payment_aging` | `etl/spark/jobs/py/billing_payment_aging.py` | `cpw.dbx_d1111_after.billing__spark_billing_payment_aging` | INVOICE_HDR.DUE_DATE unresolved in billing__invoice_hdr and billing__stg_invoice_hdr (01f1dd84-6a6d-15cb-9c0f-f1de480cb202); DAYS_LATE = datediff(payment_date, due_date) cannot be computed (`01f1dd84-6a26-13f9-be33-b99969d0d4ff`) | not run (`-`) | not run (-) | - / - | 0.005603889 (app-20261110202342-0002) | n/a (no job run) | **red** |
Red reason: INVOICE_HDR.DUE_DATE has no live equivalent (billing__invoice_hdr, billing__stg_invoice_hdr); no Databricks job created, job.sql kept as target logic
