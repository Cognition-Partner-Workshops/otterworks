CREATE SCHEMA IF NOT EXISTS cpw.dbx_d1111_after COMMENT 'run_token=dbx-d1111 expires=2026-11-24';

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.users__app_user USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_before.users__stg_app_user;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.users__user_profile USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_before.users__stg_user_profile;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.documents__doc_version USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_before.documents__stg_doc_version QUALIFY ROW_NUMBER() OVER (PARTITION BY DOCUMENT_ID ORDER BY VERSION_TS DESC) = 1;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.documents__collab_session USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_before.documents__stg_collab_session;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.documents__storage_usage_daily USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_before.documents__stg_storage_usage_daily;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__customer_account USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_before.billing__stg_customer_account;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__plan_catalog USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_before.billing__stg_plan_catalog;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__tax_rate USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_before.billing__stg_tax_rate;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__gl_account USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_before.billing__stg_gl_account;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__subscription USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_before.billing__stg_subscription;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__invoice_hdr USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_before.billing__stg_invoice_hdr;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__invoice_line USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_before.billing__stg_invoice_line;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__payment USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_before.billing__stg_payment;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__credit_note USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_before.billing__stg_credit_note;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__billing_adj USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_before.billing__stg_billing_adj;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__usage_daily USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_before.billing__stg_usage_daily;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__gl_journal_line USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_before.billing__stg_gl_journal_line;

DELETE FROM cpw.dbx_d1111_after.billing__usage_daily WHERE USAGE_TYPE='STORAGE';

INSERT INTO cpw.dbx_d1111_after.billing__usage_daily (USAGE_ID, CUSTOMER_ID, SUBSCRIPTION_ID, USAGE_DT, UNITS, USAGE_TYPE)
SELECT 10000000000 + u.CUSTOMER_ID, u.CUSTOMER_ID, s.SUBSCRIPTION_ID,
DATE '2026-11-09', u.BYTES_USED, 'STORAGE'
FROM (
SELECT CUSTOMER_ID, SUM(BYTES_USED) AS BYTES_USED FROM cpw.dbx_d1111_after.documents__storage_usage_daily
WHERE USAGE_DT >= DATE '2026-11-01'
AND USAGE_DT < DATE '2026-12-01'
GROUP BY CUSTOMER_ID
) u JOIN (
SELECT CUSTOMER_ID, MIN(SUBSCRIPTION_ID) AS SUBSCRIPTION_ID FROM cpw.dbx_d1111_after.billing__subscription GROUP BY CUSTOMER_ID
) s ON u.CUSTOMER_ID=s.CUSTOMER_ID;

DELETE FROM cpw.dbx_d1111_after.billing__invoice_line WHERE DESCRIPTION='Monthly storage';

INSERT INTO cpw.dbx_d1111_after.billing__invoice_line (INVOICE_LINE_ID, INVOICE_ID, LINE_NO, DESCRIPTION, QUANTITY, UNIT_PRICE, LINE_AMOUNT)
SELECT 11000000000+u.CUSTOMER_ID, i.INVOICE_ID, 900, 'Monthly storage', 1,
CAST(u.UNITS AS DECIMAL(20,4))/1073741824 * 0.25, CAST(u.UNITS AS DECIMAL(20,4))/1073741824 * 0.25
FROM cpw.dbx_d1111_after.billing__usage_daily u JOIN (
SELECT CUSTOMER_ID, MIN(INVOICE_ID) AS INVOICE_ID FROM cpw.dbx_d1111_after.billing__invoice_hdr GROUP BY CUSTOMER_ID
) i ON u.CUSTOMER_ID=i.CUSTOMER_ID WHERE u.USAGE_TYPE='STORAGE';

DELETE FROM cpw.dbx_d1111_after.billing__gl_journal_line;

DELETE FROM cpw.dbx_d1111_after.billing__invoice_line WHERE DESCRIPTION IN ('Monthly subscription', 'Billing adjustment');

INSERT INTO cpw.dbx_d1111_after.billing__invoice_line
(INVOICE_LINE_ID, INVOICE_ID, LINE_NO, DESCRIPTION, QUANTITY, UNIT_PRICE, LINE_AMOUNT)
SELECT 300000000000+h.INVOICE_ID, h.INVOICE_ID, 100, 'Monthly subscription', 1, p.MONTHLY_FEE, p.MONTHLY_FEE
FROM cpw.dbx_d1111_after.billing__invoice_hdr h
JOIN cpw.dbx_d1111_after.billing__subscription s ON h.SUBSCRIPTION_ID=s.SUBSCRIPTION_ID
JOIN cpw.dbx_d1111_after.billing__plan_catalog p ON s.PLAN_CODE=p.PLAN_CODE
WHERE h.INVOICE_DT <= DATE '2026-11-09';

INSERT INTO cpw.dbx_d1111_after.billing__invoice_line
(INVOICE_LINE_ID, INVOICE_ID, LINE_NO, DESCRIPTION, QUANTITY, UNIT_PRICE, LINE_AMOUNT)
SELECT 400000000000+a.ADJUSTMENT_ID, a.INVOICE_ID, 200, 'Billing adjustment', 1, a.AMOUNT, a.AMOUNT
FROM cpw.dbx_d1111_after.billing__billing_adj a
JOIN cpw.dbx_d1111_after.billing__invoice_hdr h ON a.INVOICE_ID=h.INVOICE_ID
JOIN cpw.dbx_d1111_after.billing__subscription s ON h.SUBSCRIPTION_ID=s.SUBSCRIPTION_ID
JOIN cpw.dbx_d1111_after.billing__plan_catalog p ON s.PLAN_CODE=p.PLAN_CODE
WHERE h.INVOICE_DT <= DATE '2026-11-09';

MERGE INTO cpw.dbx_d1111_after.billing__invoice_hdr i
USING (
SELECT h.INVOICE_ID, COALESCE(SUM(l.LINE_AMOUNT),0) AS SUBTOTAL_AMOUNT,
ROUND(COALESCE(SUM(l.LINE_AMOUNT),0)*MAX(t.RATE), 2) AS TAX_AMOUNT
FROM cpw.dbx_d1111_after.billing__invoice_hdr h
JOIN cpw.dbx_d1111_after.billing__subscription s ON h.SUBSCRIPTION_ID=s.SUBSCRIPTION_ID
JOIN cpw.dbx_d1111_after.billing__plan_catalog p ON s.PLAN_CODE=p.PLAN_CODE
JOIN cpw.dbx_d1111_after.billing__tax_rate t ON h.TAX_RATE_ID=t.TAX_RATE_ID
LEFT JOIN cpw.dbx_d1111_after.billing__invoice_line l ON h.INVOICE_ID=l.INVOICE_ID
WHERE h.INVOICE_DT <= DATE '2026-11-09'
GROUP BY h.INVOICE_ID
) x ON i.INVOICE_ID=x.INVOICE_ID
WHEN MATCHED THEN UPDATE SET SUBTOTAL_AMOUNT=x.SUBTOTAL_AMOUNT, TAX_AMOUNT=x.TAX_AMOUNT,
TOTAL_AMOUNT=x.SUBTOTAL_AMOUNT+x.TAX_AMOUNT;

MERGE INTO cpw.dbx_d1111_after.billing__invoice_hdr i
USING (
SELECT INVOICE_ID, SUM(TOTAL_AMOUNT) OVER (PARTITION BY CURRENCY_CD) AS CONTROL_TOTAL
FROM cpw.dbx_d1111_after.billing__invoice_hdr
) c ON i.INVOICE_ID=c.INVOICE_ID
WHEN MATCHED THEN UPDATE SET CURRENCY_CONTROL_TOTAL=c.CONTROL_TOTAL;

INSERT INTO cpw.dbx_d1111_after.billing__gl_journal_line
(JOURNAL_LINE_ID, INVOICE_ID, CREDIT_NOTE_ID, GL_ACCOUNT_ID, POSTING_DT, CURRENCY_CD, DEBIT_AMOUNT, CREDIT_AMOUNT, DESCRIPTION)
SELECT x.INVOICE_ID*10+x.LINE_NO, x.INVOICE_ID, CAST(NULL AS BIGINT), x.GL_ACCOUNT_ID, DATE '2026-11-09', x.CURRENCY_CD,
CASE WHEN x.SIGNED_AMOUNT>=0 THEN x.SIGNED_AMOUNT ELSE 0 END,
CASE WHEN x.SIGNED_AMOUNT<0 THEN -x.SIGNED_AMOUNT ELSE 0 END, 'Monthly invoice posting'
FROM (
SELECT h.INVOICE_ID, a.LINE_NO, a.GL_ACCOUNT_ID, c.CURRENCY_CD,
CASE WHEN a.GL_ACCOUNT_ID=1200 THEN h.TOTAL_AMOUNT
WHEN a.GL_ACCOUNT_ID=4000 THEN -p.MONTHLY_FEE
WHEN a.GL_ACCOUNT_ID=4100 THEN -(h.SUBTOTAL_AMOUNT-p.MONTHLY_FEE)
ELSE -h.TAX_AMOUNT END AS SIGNED_AMOUNT
FROM cpw.dbx_d1111_after.billing__invoice_hdr h
JOIN cpw.dbx_d1111_after.billing__subscription s ON h.SUBSCRIPTION_ID=s.SUBSCRIPTION_ID
JOIN cpw.dbx_d1111_after.billing__plan_catalog p ON s.PLAN_CODE=p.PLAN_CODE
JOIN (SELECT CURRENCY_CD FROM cpw.dbx_d1111_after.billing__invoice_hdr GROUP BY CURRENCY_CD) c ON h.CURRENCY_CD=c.CURRENCY_CD
CROSS JOIN (
SELECT 1 AS LINE_NO, 1200 AS GL_ACCOUNT_ID UNION ALL SELECT 2, 4000 UNION ALL SELECT 3, 4100 UNION ALL SELECT 4, 2200
) a WHERE h.INVOICE_DT <= DATE '2026-11-09'
) x;

INSERT INTO cpw.dbx_d1111_after.billing__gl_journal_line
(JOURNAL_LINE_ID, INVOICE_ID, CREDIT_NOTE_ID, GL_ACCOUNT_ID, POSTING_DT, CURRENCY_CD, DEBIT_AMOUNT, CREDIT_AMOUNT, DESCRIPTION)
SELECT 1000000000000+x.CREDIT_NOTE_ID*10+x.LINE_NO, x.INVOICE_ID, x.CREDIT_NOTE_ID, x.GL_ACCOUNT_ID, DATE '2026-11-09', x.CURRENCY_CD,
CASE WHEN x.SIGNED_AMOUNT>=0 THEN x.SIGNED_AMOUNT ELSE 0 END,
CASE WHEN x.SIGNED_AMOUNT<0 THEN -x.SIGNED_AMOUNT ELSE 0 END, 'Credit note reversal'
FROM (
SELECT h.INVOICE_ID, cr.CREDIT_NOTE_ID, a.LINE_NO, a.GL_ACCOUNT_ID, c.CURRENCY_CD,
CASE WHEN a.GL_ACCOUNT_ID=1200 THEN -cr.AMOUNT
WHEN a.GL_ACCOUNT_ID=4100 THEN ROUND(cr.AMOUNT/(1+t.RATE), 2)
ELSE cr.AMOUNT-ROUND(cr.AMOUNT/(1+t.RATE), 2) END AS SIGNED_AMOUNT
FROM cpw.dbx_d1111_after.billing__credit_note cr
JOIN cpw.dbx_d1111_after.billing__invoice_hdr h ON cr.INVOICE_ID=h.INVOICE_ID
JOIN cpw.dbx_d1111_after.billing__subscription s ON h.SUBSCRIPTION_ID=s.SUBSCRIPTION_ID
JOIN cpw.dbx_d1111_after.billing__plan_catalog p ON s.PLAN_CODE=p.PLAN_CODE
JOIN cpw.dbx_d1111_after.billing__tax_rate t ON h.TAX_RATE_ID=t.TAX_RATE_ID
JOIN (SELECT CURRENCY_CD FROM cpw.dbx_d1111_after.billing__invoice_hdr GROUP BY CURRENCY_CD) c ON h.CURRENCY_CD=c.CURRENCY_CD
CROSS JOIN (
SELECT 1 AS LINE_NO, 1200 AS GL_ACCOUNT_ID UNION ALL SELECT 2, 4100 UNION ALL SELECT 3, 2200
) a WHERE h.INVOICE_DT <= DATE '2026-11-09' AND cr.CREDIT_DT <= DATE '2026-11-09'
) x;

UPDATE cpw.dbx_d1111_after.billing__invoice_hdr SET
PRIOR_PERIOD_END_DT=INVOICE_DT - 1,
INVOICE_MONTH=(unix_date(INVOICE_DT) / 100) % 100,
PERIOD_KEY=unix_date(PERIOD_START_DT) + 19000000,
INVOICE_PERIOD=date_format(INVOICE_DT,'yyyy-MM');

UPDATE cpw.dbx_d1111_after.billing__invoice_hdr SET PERIOD_CLOSED_CD='Y'
WHERE unix_date(BILL_DT) BETWEEN 1261001 AND 1261031;

CREATE OR REPLACE VIEW cpw.dbx_d1111_after.billing__v_account_invoices COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS
SELECT a.CUSTOMER_ID, a.ACCOUNT_NAME, i.INVOICE_ID, i.INVOICE_DT, i.CURRENCY_CD, i.TOTAL_AMOUNT FROM cpw.dbx_d1111_after.billing__customer_account a JOIN cpw.dbx_d1111_after.billing__invoice_hdr i ON a.CUSTOMER_ID=i.CUSTOMER_ID;

CREATE OR REPLACE VIEW cpw.dbx_d1111_after.billing__v_subscription_plans COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS
SELECT s.SUBSCRIPTION_ID, s.CUSTOMER_ID, p.PLAN_CODE, p.MONTHLY_FEE FROM cpw.dbx_d1111_after.billing__subscription s JOIN cpw.dbx_d1111_after.billing__plan_catalog p ON s.PLAN_CODE=p.PLAN_CODE;

CREATE OR REPLACE VIEW cpw.dbx_d1111_after.billing__v_invoice_base COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS
SELECT CUSTOMER_ID, ACCOUNT_NAME, INVOICE_ID, INVOICE_DT, CURRENCY_CD, TOTAL_AMOUNT
FROM cpw.dbx_d1111_after.billing__v_account_invoices;

CREATE OR REPLACE VIEW cpw.dbx_d1111_after.billing__v_invoice_revenue COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS
SELECT CURRENCY_CD, date_format(INVOICE_DT,'yyyy-MM') AS INVOICE_PERIOD,
COUNT(*) AS INVOICE_COUNT, SUM(TOTAL_AMOUNT) AS TOTAL_AMOUNT
FROM cpw.dbx_d1111_after.billing__v_invoice_base
GROUP BY CURRENCY_CD, date_format(INVOICE_DT,'yyyy-MM');

CREATE OR REPLACE FUNCTION cpw.dbx_d1111_after.billing__m_subscription_plans_fn(p_day STRING) RETURNS TABLE COMMENT 'run_token=dbx-d1111 expires=2026-11-24' RETURN SELECT s.SUBSCRIPTION_ID, s.CUSTOMER_ID, s.PLAN_CODE, p.MONTHLY_FEE
FROM cpw.dbx_d1111_after.billing__subscription s
JOIN cpw.dbx_d1111_after.billing__plan_catalog p ON s.PLAN_CODE = p.PLAN_CODE;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__m_subscription_plans USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_after.billing__m_subscription_plans_fn('20261109');

CREATE OR REPLACE FUNCTION cpw.dbx_d1111_after.billing__m_currency_totals_fn(p_day STRING) RETURNS TABLE COMMENT 'run_token=dbx-d1111 expires=2026-11-24' RETURN SELECT CURRENCY_CD, COUNT(*) AS INVOICE_COUNT, SUM(TOTAL_AMOUNT) AS TOTAL_AMOUNT
FROM cpw.dbx_d1111_after.billing__invoice_hdr
GROUP BY CURRENCY_CD;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__m_currency_totals USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_after.billing__m_currency_totals_fn('20261109');

CREATE OR REPLACE FUNCTION cpw.dbx_d1111_after.documents__m_storage_totals_fn(p_start DATE, p_end DATE) RETURNS TABLE COMMENT 'run_token=dbx-d1111 expires=2026-11-24' RETURN SELECT CUSTOMER_ID, SUM(BYTES_USED) AS BYTES_USED, SUM(OBJECT_COUNT) AS OBJECT_COUNT
FROM cpw.dbx_d1111_after.documents__storage_usage_daily
WHERE USAGE_DT >= p_start AND USAGE_DT < p_end
GROUP BY CUSTOMER_ID;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.documents__m_storage_totals USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_after.documents__m_storage_totals_fn(DATE '2026-11-01', DATE '2026-12-01');
