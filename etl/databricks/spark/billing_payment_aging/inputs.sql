-- run_token=dbx-d1111 expires=2026-11-24
-- Input adapter: live cpw.dbx_d1111_before (Teradata-style names) -> Spark landing layout
-- (etl/spark/jobs/py/common/schemas.py). One SELECT per landing table; "-- landing:" names the PSV dir.
-- Columns without a defensible live equivalent are NULL and listed as unmapped.
-- Spark reads JDBC sfx_billing.PAYMENT / INVOICE_HDR (loaded from these landing tables by load_tdemu.sh).
-- FIRST FAILURE: INVOICE_HDR.DUE_DATE (required: DAYS_LATE = datediff(payment_date, due_date)) has no live
-- equivalent in billing__invoice_hdr nor billing__stg_invoice_hdr (warehouse/teradata/ddl/billing/00_tables.sql).
-- Failing statements: 01f1dd84-6a26-13f9-be33-b99969d0d4ff, 01f1dd84-6a6d-15cb-9c0f-f1de480cb202.

-- landing: billing/INVOICE_HDR
/* run=dbx-d1111 act=spark step=inputs consumer=billing_payment_aging */
SELECT invoice_id AS INVOICE_ID, customer_id AS CUSTOMER_ID, invoice_number AS INVOICE_NUMBER,
       invoice_dt AS INVOICE_DATE,
       CAST(NULL AS DATE) AS DUE_DATE,          -- unmapped: live invoice_hdr has no due date
       currency_cd AS CURRENCY_CODE, CAST(total_amount AS DECIMAL(18,2)) AS TOTAL_AMOUNT,
       CAST(NULL AS STRING) AS STATUS            -- unmapped: no invoice status column live
FROM cpw.dbx_d1111_before.billing__invoice_hdr;

-- landing: billing/PAYMENT
/* run=dbx-d1111 act=spark step=inputs consumer=billing_payment_aging */
SELECT payment_id AS PAYMENT_ID, invoice_id AS INVOICE_ID, customer_id AS CUSTOMER_ID, payment_dt AS PAYMENT_DATE,
       CAST(amount AS DECIMAL(18,2)) AS AMOUNT,
       CAST(NULL AS STRING) AS STATUS            -- unmapped: no payment status column live
FROM cpw.dbx_d1111_before.billing__payment;
