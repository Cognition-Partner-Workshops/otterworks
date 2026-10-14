-- Staging for pkg_billing_invoices: replaces the SSIS data flow that lands stg.stg_billing_invoices.
-- billing_invoice_lines.csv -> LKP Invoice header (invoice_id = id) -> LKP Rating period
-- (period_id = id) -> DER Normalise timestamps -> OLE DB destination.
-- The package maps a non-existent input column `line_id` (the file's column is `id`), so SQL
-- Server lands an empty string for every line; var pkg_billing_invoices_map_line_id restores `id`.
with lines as (
    select * from {{ source('pkg_billing_invoices', 'EXT_BILLING_INVOICE_LINES') }}
),

invoices as (
    select * from {{ source('pkg_billing_invoices', 'EXT_BILLING_INVOICES') }}
),

periods as (
    select * from {{ source('pkg_billing_invoices', 'EXT_BILLING_RATING_PERIODS') }}
)

select
    lines.invoice_id::varchar(36) as invoice_id,
    invoices.tenant_id::varchar(36) as tenant_id,
    to_date(to_timestamp_ntz(periods.period_start)) as period_start,
    to_date(to_timestamp_ntz(periods.period_end)) as period_end,
    to_timestamp_ntz(replace(invoices.issued_at, '+00', '')) as issued_at,
    invoices.subtotal::number(12, 2) as subtotal,
    invoices.tax::number(12, 2) as tax,
    invoices.total::number(12, 2) as total,
    invoices.status::varchar(20) as status,
    {% if var('pkg_billing_invoices_map_line_id', false) -%}
    lines.id::varchar(36)
    {%- else -%}
    ''::varchar(36)
    {%- endif %} as line_id,
    lines.line_no::integer as line_no,
    lines.line_type::varchar(20) as line_type,
    lines.description::varchar(400) as description,
    lines.amount::number(12, 2) as amount,
    convert_timezone('America/New_York', current_timestamp())::timestamp_ntz as extracted_at,
    'legacy-billing'::varchar(40) as source_system
from lines
-- SSIS Lookups fail the package on no match; left joins keep such a line visible so the
-- not_null tests on the looked-up columns fail the build the same way.
left join invoices
    on lines.invoice_id = invoices.id
left join periods
    on invoices.period_id = periods.id
