/* run=dbx-d1111 act=spark step=inputs consumer=billing_gl_trial_balance */
-- run_token=dbx-d1111 expires=2026-11-24
-- Input adapter: live cpw.dbx_d1111_before (Teradata-style names) -> Spark landing layout
-- (etl/spark/jobs/py/common/schemas.py). One SELECT per landing table; "-- landing:" names the PSV dir.
-- Columns without a defensible live equivalent are NULL and listed as unmapped.
-- FIRST FAILURE: CREDIT_NOTE.GL_ACCOUNT_ID and CREDIT_NOTE.CURRENCY_CODE (group/join keys of the adjustments CTE)
-- have no live equivalent in billing__credit_note nor billing__stg_credit_note. The live journal posts each credit
-- note to three accounts (1200/4100/2200), so no single GL account can be chosen without inventing a rule.
-- Failing statements: 01f1dd84-6ab0-109a-86d0-5ae28572a958, 01f1dd84-6b1a-15ac-8cca-5ac2f821ae5c.

-- landing: billing/GL_ACCOUNT
SELECT gl_account_id AS GL_ACCOUNT_ID, account_number AS ACCOUNT_CODE, account_name AS ACCOUNT_NAME, account_type AS ACCOUNT_TYPE
FROM cpw.dbx_d1111_before.billing__gl_account;

/* run=dbx-d1111 act=spark step=inputs consumer=billing_gl_trial_balance */
-- landing: billing/GL_JOURNAL_LINE
SELECT journal_line_id AS GL_JOURNAL_LINE_ID, CAST(NULL AS BIGINT) AS JOURNAL_ID, CAST(NULL AS BIGINT) AS LINE_NO,
       gl_account_id AS GL_ACCOUNT_ID, CAST(debit_amount AS DECIMAL(18,2)) AS DEBIT_AMT,
       CAST(credit_amount AS DECIMAL(18,2)) AS CREDIT_AMT, currency_cd AS CURRENCY_CODE, posting_dt AS POSTING_DATE,
       CAST(NULL AS STRING) AS SOURCE, CAST(NULL AS BIGINT) AS CUSTOMER_ID, invoice_id AS INVOICE_ID
FROM cpw.dbx_d1111_before.billing__gl_journal_line;

-- landing: billing/CREDIT_NOTE (cannot be adapted: GL_ACCOUNT_ID, CURRENCY_CODE unmapped)
