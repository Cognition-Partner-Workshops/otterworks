/* run=dbx-d1111 act=spark step=ddl consumer=billing_usage_append_daily */
-- run_token=dbx-d1111 expires=2026-11-24
-- Migrated from etl/spark/jobs/py/billing_usage_append_daily.py (Databricks SQL, serverless warehouse).
-- The Spark job appended the latest USAGE_DATE slice (lake + JDBC mode=append), so every rerun duplicated it.
-- Here the slice is MERGEd on the business key USAGE_ID: history accumulates across days like the append,
-- a rerun inserts and updates nothing. AMOUNT has no live source and stays NULL (see inputs.sql).
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.billing__spark_billing_usage_append_daily (
  USAGE_ID BIGINT, CUSTOMER_ID BIGINT, USAGE_DATE DATE, UNITS BIGINT, AMOUNT DECIMAL(18,2))
COMMENT 'run_token=dbx-d1111 expires=2026-11-24 source=etl/spark/jobs/py/billing_usage_append_daily.py'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark');

/* run=dbx-d1111 act=spark step=run consumer=billing_usage_append_daily */
MERGE INTO cpw.dbx_d1111_after.billing__spark_billing_usage_append_daily t
USING (
  SELECT usage_id AS USAGE_ID, customer_id AS CUSTOMER_ID, usage_dt AS USAGE_DATE, units AS UNITS,
         CAST(NULL AS DECIMAL(18,2)) AS AMOUNT
  FROM cpw.dbx_d1111_before.billing__usage_daily
  WHERE usage_dt = (SELECT MAX(usage_dt) FROM cpw.dbx_d1111_before.billing__usage_daily)
) s
ON t.USAGE_ID = s.USAGE_ID
WHEN MATCHED AND NOT (t.CUSTOMER_ID <=> s.CUSTOMER_ID AND t.USAGE_DATE <=> s.USAGE_DATE
                      AND t.UNITS <=> s.UNITS AND t.AMOUNT <=> s.AMOUNT)
  THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
