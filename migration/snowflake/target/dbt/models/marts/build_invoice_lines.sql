-- dbo.usp_build_invoice_lines: invoice lines for every invoice issued so far in the business
-- month, in cents. CAST(amount * 100 AS int) truncates toward zero; trunc() does the same.
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='business_date') }}

select
    {{ business_date() }} as business_date,
    invoices.invoice_id,
    invoices.line_no,
    invoices.tenant_id,
    invoices.period_start,
    invoices.period_end,
    invoices.line_type,
    invoices.description,
    trunc(invoices.amount * 100)::integer as amount_cents,
    invoices.status as invoice_status,
    current_timestamp()::timestamp_ntz as loaded_at
from {{ ref('stg_billing_invoices') }} as invoices
where invoices.issued_at >= date_trunc('month', {{ business_date() }})
  and invoices.issued_at < dateadd(day, 1, {{ business_date() }})
