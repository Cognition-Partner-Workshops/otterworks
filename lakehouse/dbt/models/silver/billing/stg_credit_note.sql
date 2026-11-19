select
    cast(credit_note_id as bigint) as credit_note_id,
    cast(invoice_id as bigint) as invoice_id,
    cast(customer_id as bigint) as customer_id,
    cast(credit_dt as date) as credit_dt,
    cast(amount as decimal(14,2)) as amount,
    case when length(reason_cd) > 200 then raise_error('staging reason_cd exceeds 200 characters') else reason_cd end as reason_cd,
    case when length(credit_number) > 200 then raise_error('staging credit_number exceeds 200 characters') else credit_number end as credit_number,
    case when length(reason_text) > 200 then raise_error('staging reason_text exceeds 200 characters') else reason_text end as reason_text
from {{ source('bronze_billing', 'credit_note') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
