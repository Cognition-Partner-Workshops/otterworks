select
    cast(payment_id as bigint) as payment_id,
    cast(invoice_id as bigint) as invoice_id,
    cast(customer_id as bigint) as customer_id,
    cast(payment_dt as date) as payment_dt,
    cast(amount as decimal(14,2)) as amount,
    {{ legacy_text('method_cd', 12, true) }} as method_cd,
    {{ legacy_text('payment_reference', 32) }} as payment_reference
from {{ ref('stg_payment') }}
