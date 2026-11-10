-- CAST(amount * 100 AS int) in T-SQL truncates, it doesn't round.
with month_invoices as (
    select distinct "invoice_id" as invoice_id
    from {{ source('raw', 'STG_BILLING_INVOICES') }}
    where "issued_at" >= date_trunc(month, {{ business_date() }})
      and "issued_at" < dateadd(day, 1, {{ business_date() }})
)

select
    {{ business_date() }} as business_date,
    lines."invoice_id" as invoice_id,
    lines."line_no" as line_no,
    lines."tenant_id" as tenant_id,
    lines."period_start" as period_start,
    lines."period_end" as period_end,
    lines."line_type" as line_type,
    lines."description" as description,
    trunc(lines."amount" * 100)::integer as amount_cents,
    lines."status" as invoice_status
from {{ source('raw', 'STG_BILLING_INVOICES') }} as lines
join month_invoices
    on month_invoices.invoice_id = lines."invoice_id"
