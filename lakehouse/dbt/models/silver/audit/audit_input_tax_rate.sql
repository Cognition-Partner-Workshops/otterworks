{{ config(materialized='ephemeral') }}
select
    cast(tax_rate_id as bigint) as tax_rate_id,
    {{ legacy_text('country_cd', 2, true) }} as country_cd,
    {{ legacy_text('region_cd', 20) }} as region_cd,
    cast(rate as decimal(9,6)) as rate,
    cast(effective_dt as date) as effective_dt
from {{ source('bronze_billing', 'tax_rate') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
