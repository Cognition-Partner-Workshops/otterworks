select
    cast(payment_id as bigint) as payment_id,
    cast(invoice_id as bigint) as invoice_id,
    cast(customer_id as bigint) as customer_id,
    cast(payment_dt as date) as payment_dt,
    cast(amount as decimal(14,2)) as amount,
    case when length(method_cd) > 200 then raise_error('staging method_cd exceeds 200 characters') else method_cd end as method_cd,
    case when length(payment_reference) > 200 then raise_error('staging payment_reference exceeds 200 characters') else payment_reference end as payment_reference
from {{ source('bronze_billing', 'payment') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
