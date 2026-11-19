{{ config(materialized='ephemeral') }}
select
    cast(invoice_line_id as bigint) as invoice_line_id,
    cast(invoice_id as bigint) as invoice_id,
    cast(line_no as int) as line_no,
    {{ legacy_text('description', 120) }} as description,
    cast(quantity as int) as quantity,
    cast(unit_price as decimal(18,2)) as unit_price,
    cast(line_amount as decimal(18,2)) as line_amount
from {{ source('bronze_billing', 'invoice_line') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
