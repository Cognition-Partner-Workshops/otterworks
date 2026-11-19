select
    cast(adjustment_id as bigint) as adjustment_id,
    cast(customer_id as bigint) as customer_id,
    cast(invoice_id as bigint) as invoice_id,
    cast(adjustment_dt as date) as adjustment_dt,
    cast(amount as decimal(14,2)) as amount,
    case when length(reason_cd) > 200 then raise_error('staging reason_cd exceeds 200 characters') else reason_cd end as reason_cd
from {{ source('bronze_billing', 'billing_adj') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
