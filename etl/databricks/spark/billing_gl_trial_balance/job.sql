-- run_token=dbx-d1111 expires=2026-11-24
-- Migrated from etl/spark/jobs/py/billing_gl_trial_balance.py (Databricks SQL, serverless warehouse).
-- NOT EXECUTED: live billing__credit_note / billing__stg_credit_note have no gl_account_id or currency code
-- (see inputs.sql), so the adjustments CTE cannot be sourced. Kept as the target logic once they exist.
-- Full rebuild: CREATE OR REPLACE TABLE ... AS (Spark used mode=overwrite).
/* run=dbx-d1111 act=spark step=run consumer=billing_gl_trial_balance */
CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__spark_billing_gl_trial_balance
COMMENT 'run_token=dbx-d1111 expires=2026-11-24 source=etl/spark/jobs/py/billing_gl_trial_balance.py'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24','act'='spark')
AS
WITH ledger AS (
  SELECT gl_account_id AS GL_ACCOUNT_ID, date_format(posting_dt, 'yyyy-MM') AS PERIOD, currency_cd AS CURRENCY_CODE,
         SUM(debit_amount) AS DEBITS, SUM(credit_amount) AS CREDITS, SUM(debit_amount - credit_amount) AS NET
  FROM cpw.dbx_d1111_before.billing__gl_journal_line
  GROUP BY gl_account_id, date_format(posting_dt, 'yyyy-MM'), currency_cd
), adjustments AS (
  SELECT gl_account_id AS GL_ACCOUNT_ID, date_format(credit_dt, 'yyyy-MM') AS PERIOD, currency_cd AS CURRENCY_CODE,
         SUM(amount) AS CREDIT_NOTE_ADJUSTMENTS
  FROM cpw.dbx_d1111_before.billing__credit_note
  GROUP BY gl_account_id, date_format(credit_dt, 'yyyy-MM'), currency_cd
), periods AS (
  SELECT GL_ACCOUNT_ID, PERIOD, CURRENCY_CODE FROM ledger
  UNION
  SELECT GL_ACCOUNT_ID, PERIOD, CURRENCY_CODE FROM adjustments
)
SELECT a.gl_account_id AS GL_ACCOUNT_ID, a.account_number AS ACCOUNT_CODE, a.account_name AS ACCOUNT_NAME,
       a.account_type AS ACCOUNT_TYPE, p.PERIOD, p.CURRENCY_CODE,
       coalesce(l.DEBITS, 0) AS DEBITS, coalesce(l.CREDITS, 0) AS CREDITS, coalesce(l.NET, 0) AS NET,
       coalesce(c.CREDIT_NOTE_ADJUSTMENTS, 0) AS CREDIT_NOTE_ADJUSTMENTS
FROM periods p JOIN cpw.dbx_d1111_before.billing__gl_account a ON p.GL_ACCOUNT_ID = a.gl_account_id
LEFT JOIN ledger l ON p.GL_ACCOUNT_ID = l.GL_ACCOUNT_ID AND p.PERIOD = l.PERIOD AND p.CURRENCY_CODE = l.CURRENCY_CODE
LEFT JOIN adjustments c ON p.GL_ACCOUNT_ID = c.GL_ACCOUNT_ID AND p.PERIOD = c.PERIOD AND p.CURRENCY_CODE = c.CURRENCY_CODE;
