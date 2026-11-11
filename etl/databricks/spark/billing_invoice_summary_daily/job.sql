-- run_token=dbx-d1111 expires=2026-11-24
-- Migrated from etl/spark/jobs/py/billing_invoice_summary_daily.py (Databricks SQL, serverless warehouse).
-- Full rebuild: CREATE OR REPLACE TABLE ... AS (idempotent; Spark used mode=overwrite).
-- Live column mapping follows inputs.sql (invoice_dt -> INVOICE_DATE, line_amount -> AMOUNT DECIMAL(18,2)).
/* run=dbx-d1111 act=spark step=run consumer=billing_invoice_summary_daily */
CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__spark_billing_invoice_summary_daily
COMMENT 'run_token=dbx-d1111 expires=2026-11-24 source=etl/spark/jobs/py/billing_invoice_summary_daily.py'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
AS
SELECT h.customer_id AS CUSTOMER_ID, h.invoice_dt AS INVOICE_DATE,
       COUNT(*) AS LINE_COUNT, SUM(CAST(l.line_amount AS DECIMAL(18,2))) AS AMOUNT
FROM cpw.dbx_d1111_before.billing__invoice_hdr h
JOIN cpw.dbx_d1111_before.billing__invoice_line l ON h.invoice_id = l.invoice_id
GROUP BY h.customer_id, h.invoice_dt;
