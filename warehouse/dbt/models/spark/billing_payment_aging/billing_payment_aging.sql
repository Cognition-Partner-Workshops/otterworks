-- Replaces lake billing/billing_payment_aging. One row per invoice and matching payment;
-- invoices without a payment keep null DAYS_LATE and PAID_AMOUNT.
select
    h.CUSTOMER_ID,
    h.INVOICE_ID,
    datediff(day, h.DUE_DATE, p.PAYMENT_DATE) as DAYS_LATE,
    h.TOTAL_AMOUNT,
    p.AMOUNT as PAID_AMOUNT
from {{ source('spark_billing', 'INVOICE_HDR') }} h
left join {{ source('spark_billing', 'PAYMENT') }} p
    on h.INVOICE_ID = p.INVOICE_ID
