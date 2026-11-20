{{ config(materialized='incremental', incremental_strategy='merge', unique_key='INVOICE_ID') }}

select s.INVOICE_ID, s.CUSTOMER_ID, s.SUBSCRIPTION_ID, s.INVOICE_DT, s.BILL_DT, s.PERIOD_START_DT, s.CURRENCY_CD, s.TOTAL_AMOUNT, s.INVOICE_NUMBER, s.TAX_RATE_ID, s.SUBTOTAL_AMOUNT, s.TAX_AMOUNT, s.INVOICE_PERIOD, s.PERIOD_KEY, s.PRIOR_PERIOD_END_DT, s.INVOICE_MONTH, s.PERIOD_CLOSED_CD, s.CURRENCY_CONTROL_TOTAL
from {{ ref('pc_billing__stg_invoice_hdr') }} s
where exists (select 1 from {{ ref('pc_billing__customer_account') }} c where s.CUSTOMER_ID=c.CUSTOMER_ID)
    and s.TOTAL_AMOUNT is not null and s.INVOICE_DT is not null and s.INVOICE_ID is not null
    and (s.CURRENCY_CD is null or length(s.CURRENCY_CD) <= 3)
    and (s.INVOICE_NUMBER is null or length(s.INVOICE_NUMBER) <= 32)
    and (s.INVOICE_PERIOD is null or length(s.INVOICE_PERIOD) <= 7)
    and (s.PERIOD_CLOSED_CD is null or length(s.PERIOD_CLOSED_CD) <= 1)
