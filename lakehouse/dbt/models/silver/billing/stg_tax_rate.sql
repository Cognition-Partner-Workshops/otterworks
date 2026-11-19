select
    cast(tax_rate_id as bigint) as tax_rate_id,
    case when length(country_cd) > 200 then raise_error('staging country_cd exceeds 200 characters') else country_cd end as country_cd,
    case when length(region_cd) > 200 then raise_error('staging region_cd exceeds 200 characters') else region_cd end as region_cd,
    cast(rate as decimal(7,4)) as rate,
    cast(effective_dt as date) as effective_dt
from {{ source('bronze_billing', 'tax_rate') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
