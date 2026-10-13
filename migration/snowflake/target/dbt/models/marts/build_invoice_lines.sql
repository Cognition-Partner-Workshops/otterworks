{{ config(
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="business_date"
) }}

with eligible_invoices as (
    select distinct "invoice_id" as invoice_id
    from {{ source("raw", "STG_BILLING_INVOICES") }}
    where "issued_at" >= date_trunc('month', {{ business_date() }})::date
      and "issued_at" < dateadd(day, 1, {{ business_date() }})
)

select
    {{ business_date() }} as business_date,
    i."invoice_id" as invoice_id,
    i."line_no" as line_no,
    i."tenant_id" as tenant_id,
    i."period_start" as period_start,
    i."period_end" as period_end,
    i."line_type" as line_type,
    i."description" as description,
    cast(trunc(i."amount" * 100, 0) as integer) as amount_cents,
    i."status" as invoice_status,
    current_timestamp() as loaded_at
from {{ source("raw", "STG_BILLING_INVOICES") }} as i
inner join eligible_invoices as e
    on e.invoice_id = i."invoice_id"
