/* run=dbx-d1111 act=spark step=inputs consumer=billing_invoice_summary_daily */
-- run_token=dbx-d1111 expires=2026-11-24
-- Input adapter: live cpw.dbx_d1111_before (Teradata-style names) -> Spark landing layout
-- (etl/spark/jobs/py/common/schemas.py). One SELECT per landing table; "-- landing:" names the PSV dir.
-- Columns without a defensible live equivalent are NULL and listed as unmapped.

-- landing: billing/INVOICE_HDR
SELECT invoice_id AS INVOICE_ID, customer_id AS CUSTOMER_ID, invoice_number AS INVOICE_NUMBER,
       invoice_dt AS INVOICE_DATE,
       CAST(NULL AS DATE) AS DUE_DATE,          -- unmapped: live invoice_hdr has no due date
       currency_cd AS CURRENCY_CODE, CAST(total_amount AS DECIMAL(18,2)) AS TOTAL_AMOUNT,
       CAST(NULL AS STRING) AS STATUS            -- unmapped: no invoice status column live
FROM cpw.dbx_d1111_before.billing__invoice_hdr;

/* run=dbx-d1111 act=spark step=inputs consumer=billing_invoice_summary_daily */
-- landing: billing/INVOICE_LINE

-- PLAN_ID: live invoice_line has no plan_id. warehouse/teradata/procedures/monthly_invoice.sql creates the
-- 'Monthly subscription' line from invoice_hdr.subscription_id -> subscription.plan_code -> plan_catalog.plan_code,
-- so only those lines carry a plan, usage/storage/adjustment lines get NULL (no plan).
-- plan_code match: SUBSCRIPTION.PLAN_CODE and PLAN_CATALOG.PLAN_CODE are NOT CASESPECIFIC in
-- warehouse/teradata/ddl/billing/00_tables.sql, so Teradata's s.PLAN_CODE=p.PLAN_CODE ignores case and trailing pad
-- (live has 'pro', 'Pro ', 'team'); upper(rtrim()) resolves all 500 subscriptions, trim() only 425.
SELECT l.invoice_line_id AS INVOICE_LINE_ID, l.invoice_id AS INVOICE_ID,
       CASE WHEN l.description = 'Monthly subscription' THEN p.plan_id END AS PLAN_ID,
       CAST(l.quantity AS BIGINT) AS QUANTITY, CAST(l.unit_price AS DECIMAL(18,2)) AS UNIT_PRICE,
       CAST(l.line_amount AS DECIMAL(18,2)) AS AMOUNT
FROM cpw.dbx_d1111_before.billing__invoice_line l
LEFT JOIN cpw.dbx_d1111_before.billing__invoice_hdr h ON l.invoice_id = h.invoice_id
LEFT JOIN cpw.dbx_d1111_before.billing__subscription s ON h.subscription_id = s.subscription_id
LEFT JOIN cpw.dbx_d1111_before.billing__plan_catalog p ON upper(rtrim(s.plan_code)) = upper(rtrim(p.plan_code));
