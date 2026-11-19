select
    cast(credit_note_id as bigint) as credit_note_id,
    cast(invoice_id as bigint) as invoice_id,
    cast(customer_id as bigint) as customer_id,
    cast(credit_dt as date) as credit_dt,
    cast(amount as decimal(14,2)) as amount,
    {{ legacy_text('reason_cd', 12, true) }} as reason_cd,
    {{ legacy_text('credit_number', 32) }} as credit_number,
    {{ legacy_text('reason_text', 120) }} as reason_text
from {{ ref('stg_credit_note') }}
