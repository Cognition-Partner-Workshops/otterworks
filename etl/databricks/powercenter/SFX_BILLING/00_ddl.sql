/* run=dbx-d1111 act=scale step=${STEP} consumer=m_SFX_STG_CUSTOMER_ACCOUNT */
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.billing__sfx_stg_customer_account (
  customer_id BIGINT, owner_user_id BIGINT, account_name STRING, status_cd STRING, currency_cd STRING, created_dt DATE, account_no STRING
) USING DELTA
COMMENT 'run_token=dbx-d1111 expires=2026-11-24'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24');

/* run=dbx-d1111 act=scale step=${STEP} consumer=m_SFX_CUSTOMER_ACCOUNT */
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.billing__sfx_customer_account (
  customer_id BIGINT, owner_user_id BIGINT, account_name STRING, status_cd STRING, currency_cd STRING, created_dt DATE, account_no STRING
) USING DELTA
COMMENT 'run_token=dbx-d1111 expires=2026-11-24'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24');

/* run=dbx-d1111 act=scale step=${STEP} consumer=m_SFX_STG_INVOICE_HDR */
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.billing__sfx_stg_invoice_hdr (
  invoice_id BIGINT, customer_id BIGINT, subscription_id BIGINT, invoice_dt DATE, bill_dt DATE, period_start_dt DATE, currency_cd STRING, total_amount DECIMAL(14,2), invoice_no STRING
) USING DELTA
COMMENT 'run_token=dbx-d1111 expires=2026-11-24'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24');

/* run=dbx-d1111 act=scale step=${STEP} consumer=m_SFX_INVOICE_HDR */
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.billing__sfx_invoice_hdr (
  invoice_id BIGINT, customer_id BIGINT, subscription_id BIGINT, invoice_dt DATE, bill_dt DATE, period_start_dt DATE, currency_cd STRING, total_amount DECIMAL(14,2), invoice_no STRING
) USING DELTA
COMMENT 'run_token=dbx-d1111 expires=2026-11-24'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24');

/* run=dbx-d1111 act=scale step=${STEP} consumer=m_SFX_INVOICE_LINE */
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.billing__sfx_invoice_line (
  invoice_line_id BIGINT, invoice_id BIGINT, line_no INT, description STRING, quantity INT, unit_price DECIMAL(14,2), line_amount DECIMAL(14,2)
) USING DELTA
COMMENT 'run_token=dbx-d1111 expires=2026-11-24'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24');

/* run=dbx-d1111 act=scale step=${STEP} consumer=m_SFX_PAYMENT */
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.billing__sfx_payment (
  payment_id BIGINT, invoice_id BIGINT, customer_id BIGINT, payment_dt DATE, amount DECIMAL(14,2), method_cd STRING
) USING DELTA
COMMENT 'run_token=dbx-d1111 expires=2026-11-24'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24');

/* run=dbx-d1111 act=scale step=${STEP} consumer=m_SFX_GL_JOURNAL_LINE */
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.billing__sfx_gl_journal_line (
  journal_line_id BIGINT GENERATED ALWAYS AS IDENTITY (START WITH 900001 INCREMENT BY 1), journal_no STRING, invoice_id BIGINT, gl_account_id BIGINT, posting_dt DATE, debit_amount DECIMAL(14,2), credit_amount DECIMAL(14,2), currency_cd STRING, line_desc STRING
) USING DELTA
COMMENT 'run_token=dbx-d1111 expires=2026-11-24'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24');

/* run=dbx-d1111 act=scale step=${STEP} consumer=m_SFX_INVOICE_HDR */
CREATE TABLE IF NOT EXISTS cpw.dbx_d1111_after.billing__sfx_invoice_hdr__reject (
 invoice_id BIGINT, customer_id BIGINT, subscription_id BIGINT, invoice_dt DATE, bill_dt DATE, period_start_dt DATE, currency_cd STRING, total_amount DECIMAL(14,2), invoice_no STRING, row_type INT, load_step STRING, load_date STRING
) USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24'
TBLPROPERTIES ('run_token'='dbx-d1111','expires'='2026-11-24');
