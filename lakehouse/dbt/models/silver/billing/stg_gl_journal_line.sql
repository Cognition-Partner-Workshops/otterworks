select
    cast(journal_line_id as bigint) as journal_line_id,
    cast(invoice_id as bigint) as invoice_id,
    cast(credit_note_id as bigint) as credit_note_id,
    cast(gl_account_id as bigint) as gl_account_id,
    cast(posting_dt as date) as posting_dt,
    case when length(currency_cd) > 200 then raise_error('staging currency_cd exceeds 200 characters') else currency_cd end as currency_cd,
    cast(debit_amount as decimal(14,2)) as debit_amount,
    cast(credit_amount as decimal(14,2)) as credit_amount,
    case when length(description) > 200 then raise_error('staging description exceeds 200 characters') else description end as description
from {{ source('bronze_billing', 'gl_journal_line') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
