<!-- run_token=dbx-d1111 expires=2026-11-24 -->
# billing_gl_trial_balance -> Databricks SQL (serverless)

Source `etl/spark/jobs/py/billing_gl_trial_balance.py` -> target `cpw.dbx_d1111_after.billing__spark_billing_gl_trial_balance`. Status **red**.

Files: `inputs.sql` (live -> landing adapter, one SELECT per landing table), `job.sql` (migrated logic, `sql_task` file on the serverless warehouse), `job.json` (Jobs API 2.1 settings), `parity.sql`.

## Run
Not deployed: the job is RED (see board row). `job.sql` and `job.json` are the target once the missing source column exists.

## Parity
1. Export each `inputs.sql` SELECT to `billing/<TABLE>/<yyyymmdd>.psv`, `make sfx-spark-up SFX_SPARK_LANDING=<dir>`, `make sfx-spark-run JOB=billing_gl_trial_balance SFX_SPARK_LANDING=<dir>`; History Server: `curl localhost:18080/api/v1/applications/<app>`.
2. Load `etl/spark/.data/lake/billing/billing_gl_trial_balance` into `cpw.dbx_d1111_parity.billing__spark_billing_gl_trial_balance__spark_before`.
3. Run each statement of `parity.sql` (count + order-independent hash, EXCEPT ALL both ways); after run2 re-run the count-hash statement with `step=idempotence`.

Inputs: not exported: required CREDIT_NOTE.GL_ACCOUNT_ID/CURRENCY_CODE missing.


## Query history
```sql
SELECT statement_id, start_time, total_duration_ms, read_rows, produced_rows, execution_status FROM system.query.history WHERE statement_text LIKE '/* run=dbx-d1111 act=spark step=%consumer=billing_gl_trial_balance */%' ORDER BY start_time
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
| `billing_gl_trial_balance` | `etl/spark/jobs/py/billing_gl_trial_balance.py` | `cpw.dbx_d1111_after.billing__spark_billing_gl_trial_balance` | CREDIT_NOTE.GL_ACCOUNT_ID/CURRENCY_CODE unresolved in billing__credit_note and billing__stg_credit_note (01f1dd84-6b1a-15ac-8cca-5ac2f821ae5c); all 100 credit notes post to >1 GL account in billing__gl_journal_line (01f1dd85-2c9e-1315-a4ad-815d65b44abd), so no single account is defensible (`01f1dd84-6ab0-109a-86d0-5ae28572a958`) | not run (`-`) | not run (-) | - / - | 0.006288056 (app-20261110202517-0010) | n/a (no job run) | **red** |
Red reason: CREDIT_NOTE.GL_ACCOUNT_ID and CURRENCY_CODE have no live equivalent; no Databricks job created, job.sql kept as target logic
