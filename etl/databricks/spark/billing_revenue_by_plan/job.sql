-- run_token=dbx-d1111 expires=2026-11-24
-- Migrated from etl/spark/jobs/py/billing_revenue_by_plan.py (Databricks SQL, serverless warehouse).
-- Full rebuild: CREATE OR REPLACE TABLE ... AS (idempotent; Spark used mode=overwrite).
-- INVOICE_LINE.PLAN_ID is not stored live; it is resolved exactly as inputs.sql documents
-- (only 'Monthly subscription' lines, via invoice_hdr.subscription_id -> subscription.plan_code -> plan_catalog).
/* run=dbx-d1111 act=spark step=run consumer=billing_revenue_by_plan */
CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__spark_billing_revenue_by_plan
COMMENT 'run_token=dbx-d1111 expires=2026-11-24 source=etl/spark/jobs/py/billing_revenue_by_plan.py'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
AS
WITH invoice_line AS (
  SELECT CASE WHEN l.description = 'Monthly subscription' THEN pc.plan_id END AS PLAN_ID,
         CAST(l.line_amount AS DECIMAL(18,2)) AS AMOUNT
  FROM cpw.dbx_d1111_before.billing__invoice_line l
  LEFT JOIN cpw.dbx_d1111_before.billing__invoice_hdr h ON l.invoice_id = h.invoice_id
  LEFT JOIN cpw.dbx_d1111_before.billing__subscription s ON h.subscription_id = s.subscription_id
  LEFT JOIN cpw.dbx_d1111_before.billing__plan_catalog pc ON trim(s.plan_code) = trim(pc.plan_code)
)
SELECT p.plan_id AS PLAN_ID, p.plan_name AS PLAN_NAME, SUM(l.AMOUNT) AS REVENUE
FROM invoice_line l
JOIN cpw.dbx_d1111_before.billing__plan_catalog p ON l.PLAN_ID = p.plan_id
GROUP BY p.plan_id, p.plan_name;
