select
    cast(tax_rate_id as bigint) as tax_rate_id,
    {{ legacy_text('country_cd', 2, true) }} as country_cd,
    {{ legacy_text('region_cd', 20) }} as region_cd,
    cast(rate as decimal(7,4)) as rate,
    cast(effective_dt as date) as effective_dt
from {{ ref('stg_tax_rate') }}
