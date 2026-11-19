select
    cast(invoice_line_id as bigint) as invoice_line_id,
    cast(invoice_id as bigint) as invoice_id,
    cast(line_no as integer) as line_no,
    case when length(description) > 200 then raise_error('staging description exceeds 200 characters') else description end as description,
    cast(quantity as integer) as quantity,
    cast(unit_price as decimal(14,2)) as unit_price,
    cast(line_amount as decimal(14,2)) as line_amount
from {{ source('bronze_billing', 'invoice_line') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
