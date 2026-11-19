{{ config(materialized='ephemeral') }}
select
    cast(adjustment_id as bigint) as adjustment_id,
    cast(customer_id as bigint) as customer_id,
    cast(invoice_id as bigint) as invoice_id,
    cast(adjustment_dt as date) as adjustment_dt,
    cast(amount as decimal(18,2)) as amount,
    {{ legacy_text('reason_cd', 12, true) }} as reason_cd
from {{ source('bronze_billing', 'billing_adj') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
