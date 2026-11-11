-- Replaces lake billing/billing_invoice_summary_daily and JDBC sfx_billing.SPARK_INVOICE_SUMMARY.
select
    h.CUSTOMER_ID,
    h.INVOICE_DATE,
    count(*) as LINE_COUNT,
    sum(l.AMOUNT) as AMOUNT
from {{ source('spark_billing', 'INVOICE_HDR') }} h
join {{ source('spark_billing', 'INVOICE_LINE') }} l
    on h.INVOICE_ID = l.INVOICE_ID
group by h.CUSTOMER_ID, h.INVOICE_DATE
