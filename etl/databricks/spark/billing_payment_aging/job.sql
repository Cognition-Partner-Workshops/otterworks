-- run_token=dbx-d1111 expires=2026-11-24
-- Migrated from etl/spark/jobs/py/billing_payment_aging.py (Databricks SQL, serverless warehouse).
-- NOT EXECUTED: live billing__invoice_hdr / billing__stg_invoice_hdr have no due_date (see inputs.sql), so this
-- statement fails with UNRESOLVED_COLUMN against the live baseline. Kept as the target logic once a due date exists.
-- Full rebuild: CREATE OR REPLACE TABLE ... AS (Spark used mode=overwrite). LEFT JOIN keeps unpaid invoices (NULLs).
/* run=dbx-d1111 act=spark step=run consumer=billing_payment_aging */
CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__spark_billing_payment_aging
COMMENT 'run_token=dbx-d1111 expires=2026-11-24 source=etl/spark/jobs/py/billing_payment_aging.py'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
AS
SELECT h.customer_id AS customer_id, h.invoice_id AS invoice_id,
       datediff(p.payment_dt, h.due_date) AS DAYS_LATE,
       CAST(h.total_amount AS DECIMAL(18,2)) AS total_amount, CAST(p.amount AS DECIMAL(18,2)) AS PAID_AMOUNT
FROM cpw.dbx_d1111_before.billing__invoice_hdr h
LEFT JOIN cpw.dbx_d1111_before.billing__payment p ON h.invoice_id = p.invoice_id;
