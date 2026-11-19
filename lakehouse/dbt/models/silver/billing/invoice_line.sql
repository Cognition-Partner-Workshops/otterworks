select
    cast(invoice_line_id as bigint) as invoice_line_id,
    cast(invoice_id as bigint) as invoice_id,
    cast(line_no as integer) as line_no,
    {{ legacy_text('description', 120) }} as description,
    cast(quantity as integer) as quantity,
    cast(unit_price as decimal(14,2)) as unit_price,
    cast(line_amount as decimal(14,2)) as line_amount
from {{ ref('stg_invoice_line') }}
