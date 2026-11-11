CREATE SCHEMA IF NOT EXISTS cpw.dbx_d1111_after COMMENT 'run_token=dbx-d1111 expires=2026-11-24';

CREATE OR REPLACE FUNCTION cpw.dbx_d1111_after.billing__td_date_int(d DATE) RETURNS INT COMMENT 'run_token=dbx-d1111 expires=2026-11-24' RETURN (year(d)-1900)*10000+month(d)*100+day(d);

CREATE OR REPLACE FUNCTION cpw.dbx_d1111_after.billing__td_int_date(n INT) RETURNS DATE COMMENT 'run_token=dbx-d1111 expires=2026-11-24' RETURN make_date((n DIV 10000)+1900,(n DIV 100)%100,n%100);

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__in_users_app_user USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT USER_ID AS USER_ID, substring(DISPLAY_NAME,1,60) AS DISPLAY_NAME, substring(EMAIL,1,120) AS EMAIL, rpad(substring(STATUS_CD,1,12),12,' ') AS STATUS_CD, CREATED_DT AS CREATED_DT FROM cpw.dbx_d1111_before.users__stg_app_user;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__in_users_user_profile USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT PROFILE_ID AS PROFILE_ID, USER_ID AS USER_ID, substring(TITLE,1,60) AS TITLE, rpad(substring(COUNTRY_CD,1,2),2,' ') AS COUNTRY_CD, substring(TIMEZONE,1,40) AS TIMEZONE FROM cpw.dbx_d1111_before.users__stg_user_profile;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__in_documents_doc_version USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT VERSION_ID AS VERSION_ID, DOCUMENT_ID AS DOCUMENT_ID, VERSION_NO AS VERSION_NO, VERSION_TS AS VERSION_TS, FILE_SIZE AS FILE_SIZE, substring(CONTENT_HASH,1,64) AS CONTENT_HASH FROM cpw.dbx_d1111_before.documents__stg_doc_version QUALIFY ROW_NUMBER() OVER (PARTITION BY DOCUMENT_ID ORDER BY VERSION_TS DESC, VERSION_NO DESC, VERSION_ID DESC) = 1;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__in_documents_collab_session USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT SESSION_ID AS SESSION_ID, DOCUMENT_ID AS DOCUMENT_ID, USER_ID AS USER_ID, START_TS AS START_TS, END_TS AS END_TS FROM cpw.dbx_d1111_before.documents__stg_collab_session;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__in_documents_storage_usage_daily USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT DISTINCT STORAGE_USAGE_ID AS STORAGE_USAGE_ID, CUSTOMER_ID AS CUSTOMER_ID, OWNER_USER_ID AS OWNER_USER_ID, USAGE_DT AS USAGE_DT, BYTES_USED AS BYTES_USED, OBJECT_COUNT AS OBJECT_COUNT FROM cpw.dbx_d1111_before.documents__stg_storage_usage_daily;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__customer_account USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT CUSTOMER_ID AS CUSTOMER_ID, OWNER_USER_ID AS OWNER_USER_ID, substring(ACCOUNT_NAME,1,100) AS ACCOUNT_NAME, rpad(substring(STATUS_CD,1,12),12,' ') AS STATUS_CD, rpad(substring(CURRENCY_CD,1,3),3,' ') AS CURRENCY_CD, CREATED_DT AS CREATED_DT, substring(ACCOUNT_NUMBER,1,24) AS ACCOUNT_NUMBER, rpad(substring(COUNTRY_CD,1,2),2,' ') AS COUNTRY_CD, substring(REGION_CD,1,20) AS REGION_CD FROM cpw.dbx_d1111_before.billing__stg_customer_account;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__plan_catalog USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT PLAN_ID AS PLAN_ID, rpad(substring(PLAN_CODE,1,10),10,' ') AS PLAN_CODE, substring(PLAN_NAME,1,80) AS PLAN_NAME, MONTHLY_FEE AS MONTHLY_FEE, rpad(substring(CURRENCY_CD,1,3),3,' ') AS CURRENCY_CD FROM cpw.dbx_d1111_before.billing__stg_plan_catalog;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__tax_rate USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT TAX_RATE_ID AS TAX_RATE_ID, rpad(substring(COUNTRY_CD,1,2),2,' ') AS COUNTRY_CD, substring(REGION_CD,1,20) AS REGION_CD, RATE AS RATE, EFFECTIVE_DT AS EFFECTIVE_DT FROM cpw.dbx_d1111_before.billing__stg_tax_rate;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__gl_account USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT GL_ACCOUNT_ID AS GL_ACCOUNT_ID, rpad(substring(ACCOUNT_NUMBER,1,4),4,' ') AS ACCOUNT_NUMBER, substring(ACCOUNT_NAME,1,80) AS ACCOUNT_NAME, rpad(substring(ACCOUNT_TYPE,1,12),12,' ') AS ACCOUNT_TYPE, rpad(substring(NORMAL_BALANCE,1,2),2,' ') AS NORMAL_BALANCE FROM cpw.dbx_d1111_before.billing__stg_gl_account;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__subscription USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT SUBSCRIPTION_ID AS SUBSCRIPTION_ID, CUSTOMER_ID AS CUSTOMER_ID, substring(PLAN_CODE,1,10) AS PLAN_CODE, START_DT AS START_DT, END_DT AS END_DT, rpad(substring(STATUS_CD,1,12),12,' ') AS STATUS_CD FROM cpw.dbx_d1111_before.billing__stg_subscription;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__invoice_hdr USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT INVOICE_ID AS INVOICE_ID, CUSTOMER_ID AS CUSTOMER_ID, SUBSCRIPTION_ID AS SUBSCRIPTION_ID, INVOICE_DT AS INVOICE_DT, BILL_DT AS BILL_DT, PERIOD_START_DT AS PERIOD_START_DT, rpad(substring(CURRENCY_CD,1,3),3,' ') AS CURRENCY_CD, TOTAL_AMOUNT AS TOTAL_AMOUNT, substring(INVOICE_NUMBER,1,32) AS INVOICE_NUMBER, TAX_RATE_ID AS TAX_RATE_ID, SUBTOTAL_AMOUNT AS SUBTOTAL_AMOUNT, TAX_AMOUNT AS TAX_AMOUNT, rpad(substring(INVOICE_PERIOD,1,7),7,' ') AS INVOICE_PERIOD, PERIOD_KEY AS PERIOD_KEY, PRIOR_PERIOD_END_DT AS PRIOR_PERIOD_END_DT, INVOICE_MONTH AS INVOICE_MONTH, rpad(substring(PERIOD_CLOSED_CD,1,1),1,' ') AS PERIOD_CLOSED_CD, CURRENCY_CONTROL_TOTAL AS CURRENCY_CONTROL_TOTAL FROM cpw.dbx_d1111_before.billing__stg_invoice_hdr;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__invoice_line USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT INVOICE_LINE_ID AS INVOICE_LINE_ID, INVOICE_ID AS INVOICE_ID, LINE_NO AS LINE_NO, substring(DESCRIPTION,1,120) AS DESCRIPTION, QUANTITY AS QUANTITY, UNIT_PRICE AS UNIT_PRICE, LINE_AMOUNT AS LINE_AMOUNT FROM cpw.dbx_d1111_before.billing__stg_invoice_line;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__payment USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT PAYMENT_ID AS PAYMENT_ID, INVOICE_ID AS INVOICE_ID, CUSTOMER_ID AS CUSTOMER_ID, PAYMENT_DT AS PAYMENT_DT, AMOUNT AS AMOUNT, rpad(substring(METHOD_CD,1,12),12,' ') AS METHOD_CD, substring(PAYMENT_REFERENCE,1,32) AS PAYMENT_REFERENCE FROM cpw.dbx_d1111_before.billing__stg_payment;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__credit_note USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT CREDIT_NOTE_ID AS CREDIT_NOTE_ID, INVOICE_ID AS INVOICE_ID, CUSTOMER_ID AS CUSTOMER_ID, CREDIT_DT AS CREDIT_DT, AMOUNT AS AMOUNT, rpad(substring(REASON_CD,1,12),12,' ') AS REASON_CD, substring(CREDIT_NUMBER,1,32) AS CREDIT_NUMBER, substring(REASON_TEXT,1,120) AS REASON_TEXT FROM cpw.dbx_d1111_before.billing__stg_credit_note;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__billing_adj USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT ADJUSTMENT_ID AS ADJUSTMENT_ID, CUSTOMER_ID AS CUSTOMER_ID, INVOICE_ID AS INVOICE_ID, ADJUSTMENT_DT AS ADJUSTMENT_DT, AMOUNT AS AMOUNT, rpad(substring(REASON_CD,1,12),12,' ') AS REASON_CD FROM cpw.dbx_d1111_before.billing__stg_billing_adj;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__usage_daily USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT USAGE_ID AS USAGE_ID, CUSTOMER_ID AS CUSTOMER_ID, SUBSCRIPTION_ID AS SUBSCRIPTION_ID, USAGE_DT AS USAGE_DT, UNITS AS UNITS, rpad(substring(USAGE_TYPE,1,12),12,' ') AS USAGE_TYPE FROM cpw.dbx_d1111_before.billing__stg_usage_daily;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__gl_journal_line USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT JOURNAL_LINE_ID AS JOURNAL_LINE_ID, INVOICE_ID AS INVOICE_ID, CREDIT_NOTE_ID AS CREDIT_NOTE_ID, GL_ACCOUNT_ID AS GL_ACCOUNT_ID, POSTING_DT AS POSTING_DT, rpad(substring(CURRENCY_CD,1,3),3,' ') AS CURRENCY_CD, DEBIT_AMOUNT AS DEBIT_AMOUNT, CREDIT_AMOUNT AS CREDIT_AMOUNT, substring(DESCRIPTION,1,120) AS DESCRIPTION FROM cpw.dbx_d1111_before.billing__stg_gl_journal_line;

DELETE FROM cpw.dbx_d1111_after.billing__usage_daily WHERE rtrim(USAGE_TYPE)='STORAGE';

INSERT INTO cpw.dbx_d1111_after.billing__usage_daily (USAGE_ID, CUSTOMER_ID, SUBSCRIPTION_ID, USAGE_DT, UNITS, USAGE_TYPE)
SELECT 10000000000 + u.CUSTOMER_ID, u.CUSTOMER_ID, s.SUBSCRIPTION_ID,
DATE '2026-11-09', u.BYTES_USED, rpad('STORAGE',12,' ')
FROM (
SELECT CUSTOMER_ID, SUM(BYTES_USED) AS BYTES_USED FROM cpw.dbx_d1111_after.billing__in_documents_storage_usage_daily
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
) i ON u.CUSTOMER_ID=i.CUSTOMER_ID WHERE rtrim(u.USAGE_TYPE)='STORAGE';

DELETE FROM cpw.dbx_d1111_after.billing__gl_journal_line;

DELETE FROM cpw.dbx_d1111_after.billing__invoice_line WHERE DESCRIPTION IN ('Monthly subscription', 'Billing adjustment');

INSERT INTO cpw.dbx_d1111_after.billing__invoice_line
(INVOICE_LINE_ID, INVOICE_ID, LINE_NO, DESCRIPTION, QUANTITY, UNIT_PRICE, LINE_AMOUNT)
SELECT 300000000000+h.INVOICE_ID, h.INVOICE_ID, 100, 'Monthly subscription', 1, p.MONTHLY_FEE, p.MONTHLY_FEE
FROM cpw.dbx_d1111_after.billing__invoice_hdr h
JOIN cpw.dbx_d1111_after.billing__subscription s ON h.SUBSCRIPTION_ID=s.SUBSCRIPTION_ID
JOIN cpw.dbx_d1111_after.billing__plan_catalog p ON upper(rtrim(s.PLAN_CODE))=upper(rtrim(p.PLAN_CODE))
WHERE h.INVOICE_DT <= DATE '2026-11-09';

INSERT INTO cpw.dbx_d1111_after.billing__invoice_line
(INVOICE_LINE_ID, INVOICE_ID, LINE_NO, DESCRIPTION, QUANTITY, UNIT_PRICE, LINE_AMOUNT)
SELECT 400000000000+a.ADJUSTMENT_ID, a.INVOICE_ID, 200, 'Billing adjustment', 1, a.AMOUNT, a.AMOUNT
FROM cpw.dbx_d1111_after.billing__billing_adj a
JOIN cpw.dbx_d1111_after.billing__invoice_hdr h ON a.INVOICE_ID=h.INVOICE_ID
JOIN cpw.dbx_d1111_after.billing__subscription s ON h.SUBSCRIPTION_ID=s.SUBSCRIPTION_ID
JOIN cpw.dbx_d1111_after.billing__plan_catalog p ON upper(rtrim(s.PLAN_CODE))=upper(rtrim(p.PLAN_CODE))
WHERE h.INVOICE_DT <= DATE '2026-11-09';

MERGE INTO cpw.dbx_d1111_after.billing__invoice_hdr i
USING (
SELECT h.INVOICE_ID, COALESCE(SUM(l.LINE_AMOUNT),0) AS SUBTOTAL_AMOUNT,
ROUND(COALESCE(SUM(l.LINE_AMOUNT),0)*MAX(t.RATE), 2) AS TAX_AMOUNT
FROM cpw.dbx_d1111_after.billing__invoice_hdr h
JOIN cpw.dbx_d1111_after.billing__subscription s ON h.SUBSCRIPTION_ID=s.SUBSCRIPTION_ID
JOIN cpw.dbx_d1111_after.billing__plan_catalog p ON upper(rtrim(s.PLAN_CODE))=upper(rtrim(p.PLAN_CODE))
JOIN cpw.dbx_d1111_after.billing__tax_rate t ON h.TAX_RATE_ID=t.TAX_RATE_ID
LEFT JOIN cpw.dbx_d1111_after.billing__invoice_line l ON h.INVOICE_ID=l.INVOICE_ID
WHERE h.INVOICE_DT <= DATE '2026-11-09'
GROUP BY h.INVOICE_ID
) x ON i.INVOICE_ID=x.INVOICE_ID
WHEN MATCHED THEN UPDATE SET SUBTOTAL_AMOUNT=x.SUBTOTAL_AMOUNT, TAX_AMOUNT=x.TAX_AMOUNT,
TOTAL_AMOUNT=x.SUBTOTAL_AMOUNT+x.TAX_AMOUNT;

MERGE INTO cpw.dbx_d1111_after.billing__invoice_hdr i
USING (
SELECT INVOICE_ID, SUM(TOTAL_AMOUNT) OVER (PARTITION BY upper(rtrim(CURRENCY_CD))) AS CONTROL_TOTAL
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
JOIN cpw.dbx_d1111_after.billing__plan_catalog p ON upper(rtrim(s.PLAN_CODE))=upper(rtrim(p.PLAN_CODE))
JOIN (SELECT min_by(rtrim(CURRENCY_CD),INVOICE_ID) AS CURRENCY_CD FROM cpw.dbx_d1111_after.billing__invoice_hdr GROUP BY upper(rtrim(CURRENCY_CD))) c ON upper(rtrim(h.CURRENCY_CD))=upper(rtrim(c.CURRENCY_CD))
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
JOIN cpw.dbx_d1111_after.billing__plan_catalog p ON upper(rtrim(s.PLAN_CODE))=upper(rtrim(p.PLAN_CODE))
JOIN cpw.dbx_d1111_after.billing__tax_rate t ON h.TAX_RATE_ID=t.TAX_RATE_ID
JOIN (SELECT min_by(rtrim(CURRENCY_CD),INVOICE_ID) AS CURRENCY_CD FROM cpw.dbx_d1111_after.billing__invoice_hdr GROUP BY upper(rtrim(CURRENCY_CD))) c ON upper(rtrim(h.CURRENCY_CD))=upper(rtrim(c.CURRENCY_CD))
CROSS JOIN (
SELECT 1 AS LINE_NO, 1200 AS GL_ACCOUNT_ID UNION ALL SELECT 2, 4100 UNION ALL SELECT 3, 2200
) a WHERE h.INVOICE_DT <= DATE '2026-11-09' AND cr.CREDIT_DT <= DATE '2026-11-09'
) x;

UPDATE cpw.dbx_d1111_after.billing__invoice_hdr SET
PRIOR_PERIOD_END_DT=INVOICE_DT - 1,
INVOICE_MONTH=(cpw.dbx_d1111_after.billing__td_date_int(INVOICE_DT) DIV 100) % 100,
PERIOD_KEY=cpw.dbx_d1111_after.billing__td_date_int(PERIOD_START_DT) + 19000000,
INVOICE_PERIOD=date_format(INVOICE_DT,'yyyy-MM');

UPDATE cpw.dbx_d1111_after.billing__invoice_hdr SET PERIOD_CLOSED_CD='Y'
WHERE BILL_DT BETWEEN cpw.dbx_d1111_after.billing__td_int_date(1261001) AND cpw.dbx_d1111_after.billing__td_int_date(1261031);

CREATE OR REPLACE VIEW cpw.dbx_d1111_after.billing__v_account_invoices COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS
SELECT a.CUSTOMER_ID, a.ACCOUNT_NAME, i.INVOICE_ID, i.INVOICE_DT, i.CURRENCY_CD, i.TOTAL_AMOUNT FROM cpw.dbx_d1111_after.billing__customer_account a JOIN cpw.dbx_d1111_after.billing__invoice_hdr i ON a.CUSTOMER_ID=i.CUSTOMER_ID;

CREATE OR REPLACE VIEW cpw.dbx_d1111_after.billing__v_subscription_plans COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS
SELECT s.SUBSCRIPTION_ID, s.CUSTOMER_ID, p.PLAN_CODE, p.MONTHLY_FEE FROM cpw.dbx_d1111_after.billing__subscription s JOIN cpw.dbx_d1111_after.billing__plan_catalog p ON upper(rtrim(s.PLAN_CODE))=upper(rtrim(p.PLAN_CODE));

CREATE OR REPLACE VIEW cpw.dbx_d1111_after.billing__v_invoice_base COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS
SELECT CUSTOMER_ID, ACCOUNT_NAME, INVOICE_ID, INVOICE_DT, CURRENCY_CD, TOTAL_AMOUNT
FROM cpw.dbx_d1111_after.billing__v_account_invoices;

CREATE OR REPLACE VIEW cpw.dbx_d1111_after.billing__v_invoice_revenue COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS
SELECT min_by(rtrim(CURRENCY_CD),INVOICE_ID) AS CURRENCY_CD, date_format(INVOICE_DT,'yyyy-MM') AS INVOICE_PERIOD,
COUNT(*) AS INVOICE_COUNT, SUM(TOTAL_AMOUNT) AS TOTAL_AMOUNT
FROM cpw.dbx_d1111_after.billing__v_invoice_base
GROUP BY upper(rtrim(CURRENCY_CD)), date_format(INVOICE_DT,'yyyy-MM');

CREATE OR REPLACE FUNCTION cpw.dbx_d1111_after.billing__m_subscription_plans_fn(p_day STRING) RETURNS TABLE COMMENT 'run_token=dbx-d1111 expires=2026-11-24' RETURN SELECT s.SUBSCRIPTION_ID, s.CUSTOMER_ID, s.PLAN_CODE, p.MONTHLY_FEE
FROM cpw.dbx_d1111_after.billing__subscription s
JOIN cpw.dbx_d1111_after.billing__plan_catalog p ON upper(rtrim(s.PLAN_CODE)) = upper(rtrim(p.PLAN_CODE));

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__m_subscription_plans USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_after.billing__m_subscription_plans_fn('20261109');

CREATE OR REPLACE FUNCTION cpw.dbx_d1111_after.billing__m_currency_totals_fn(p_day STRING) RETURNS TABLE COMMENT 'run_token=dbx-d1111 expires=2026-11-24' RETURN SELECT min_by(rtrim(CURRENCY_CD),INVOICE_ID) AS CURRENCY_CD, COUNT(*) AS INVOICE_COUNT, SUM(TOTAL_AMOUNT) AS TOTAL_AMOUNT
FROM cpw.dbx_d1111_after.billing__invoice_hdr
GROUP BY upper(rtrim(CURRENCY_CD));

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__m_currency_totals USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_after.billing__m_currency_totals_fn('20261109');

CREATE OR REPLACE FUNCTION cpw.dbx_d1111_after.billing__in_documents_m_storage_totals_fn(p_start DATE, p_end DATE) RETURNS TABLE COMMENT 'run_token=dbx-d1111 expires=2026-11-24' RETURN SELECT CUSTOMER_ID, SUM(BYTES_USED) AS BYTES_USED, SUM(OBJECT_COUNT) AS OBJECT_COUNT
FROM cpw.dbx_d1111_after.billing__in_documents_storage_usage_daily
WHERE USAGE_DT >= p_start AND USAGE_DT < p_end
GROUP BY CUSTOMER_ID;

CREATE OR REPLACE TABLE cpw.dbx_d1111_after.billing__in_documents_m_storage_totals USING DELTA COMMENT 'run_token=dbx-d1111 expires=2026-11-24' AS SELECT * FROM cpw.dbx_d1111_after.billing__in_documents_m_storage_totals_fn(DATE '2026-11-01', DATE '2026-12-01');
