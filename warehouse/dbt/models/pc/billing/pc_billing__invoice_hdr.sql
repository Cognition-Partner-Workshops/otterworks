{{ config(materialized='incremental', incremental_strategy='merge', unique_key='INVOICE_ID') }}

with customers as (
    select CUSTOMER_ID
    from {{ ref('pc_billing__customer_account') }}
    qualify row_number() over (partition by CUSTOMER_ID order by CUSTOMER_ID) = 1
)
select
    s.INVOICE_ID::number(19,0) as INVOICE_ID,
    s.CUSTOMER_ID::number(19,0) as CUSTOMER_ID,
    s.SUBSCRIPTION_ID::number(19,0) as SUBSCRIPTION_ID,
    s.INVOICE_DT::date as INVOICE_DT,
    s.BILL_DT::date as BILL_DT,
    s.PERIOD_START_DT::date as PERIOD_START_DT,
    s.CURRENCY_CD::varchar(3) as CURRENCY_CD,
    s.TOTAL_AMOUNT::number(14,2) as TOTAL_AMOUNT,
    s.INVOICE_NO::varchar(20) as INVOICE_NO
from {{ ref('pc_billing__stg_invoice_hdr') }} s
left join customers c on s.CUSTOMER_ID = c.CUSTOMER_ID
where c.CUSTOMER_ID is not null and s.TOTAL_AMOUNT is not null and s.INVOICE_DT is not null
    and s.INVOICE_ID is not null
    and (s.CURRENCY_CD is null or length(s.CURRENCY_CD) <= 3)
    and (s.INVOICE_NO is null or length(s.INVOICE_NO) <= 20)
qualify row_number() over (partition by s.INVOICE_ID order by s.SRC_ROW_NO) = 1
