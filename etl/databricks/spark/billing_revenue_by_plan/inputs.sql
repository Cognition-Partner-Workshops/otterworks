-- run_token=dbx-d1111 expires=2026-11-24
-- Input adapter: live cpw.dbx_d1111_before (Teradata-style names) -> Spark landing layout
-- (etl/spark/jobs/py/common/schemas.py). One SELECT per landing table; "-- landing:" names the PSV dir.
-- Columns without a defensible live equivalent are NULL and listed as unmapped.

-- landing: billing/INVOICE_LINE
/* run=dbx-d1111 act=spark step=inputs consumer=billing_revenue_by_plan */
-- PLAN_ID: live invoice_line has no plan_id. warehouse/teradata/procedures/monthly_invoice.sql creates the
-- 'Monthly subscription' line from invoice_hdr.subscription_id -> subscription.plan_code -> plan_catalog.plan_code,
-- so only those lines carry a plan, usage/storage/adjustment lines get NULL (no plan).
SELECT l.invoice_line_id AS INVOICE_LINE_ID, l.invoice_id AS INVOICE_ID,
       CASE WHEN l.description = 'Monthly subscription' THEN p.plan_id END AS PLAN_ID,
       CAST(l.quantity AS BIGINT) AS QUANTITY, CAST(l.unit_price AS DECIMAL(18,2)) AS UNIT_PRICE,
       CAST(l.line_amount AS DECIMAL(18,2)) AS AMOUNT
FROM cpw.dbx_d1111_before.billing__invoice_line l
LEFT JOIN cpw.dbx_d1111_before.billing__invoice_hdr h ON l.invoice_id = h.invoice_id
LEFT JOIN cpw.dbx_d1111_before.billing__subscription s ON h.subscription_id = s.subscription_id
LEFT JOIN cpw.dbx_d1111_before.billing__plan_catalog p ON trim(s.plan_code) = trim(p.plan_code);

-- landing: billing/PLAN_CATALOG
/* run=dbx-d1111 act=spark step=inputs consumer=billing_revenue_by_plan */
SELECT plan_id AS PLAN_ID, plan_name AS PLAN_NAME, CAST(monthly_fee AS DECIMAL(18,2)) AS MONTHLY_PRICE
FROM cpw.dbx_d1111_before.billing__plan_catalog;
