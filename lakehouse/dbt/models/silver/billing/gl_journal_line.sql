{% set previous = adapter.get_relation(database=this.database, schema=this.schema, identifier=this.identifier) if execute else none %}
with incoming as (
select
    cast(journal_line_id as bigint) as journal_line_id,
    cast(invoice_id as bigint) as invoice_id,
    cast(credit_note_id as bigint) as credit_note_id,
    cast(gl_account_id as bigint) as gl_account_id,
    cast(posting_dt as date) as posting_dt,
    {{ legacy_text('currency_cd', 3, true) }} as currency_cd,
    cast(debit_amount as decimal(14,2)) as debit_amount,
    cast(credit_amount as decimal(14,2)) as credit_amount,
    {{ legacy_text('description', 120) }} as description
from {{ ref('stg_gl_journal_line') }}
)
{% if previous is not none %}
select * from {{ this }}
union all
select s.* from incoming s
where not exists (select 1 from {{ this }} p where p.posting_dt = s.posting_dt)
{% else %}
select * from incoming
{% endif %}
