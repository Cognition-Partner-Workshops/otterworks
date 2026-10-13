{{ config(
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="business_date"
) }}

with rated as (
    select
        f.business_date,
        f.tenant_id,
        p.overage_cents_per_gb,
        case
            when p.plan_id is null then null
            when f.bytes_used > f.included_bytes
                then cast(trunc((f.bytes_used - f.included_bytes) / 1073741824, 0) as integer)
            else 0
        end as overage_gb
    from {{ ref("rollup_storage_daily") }} as f
    left join {{ ref("dim_plan") }} as p
        on p.plan_id = f.plan_id
    where f.business_date = {{ business_date() }}
)

select
    business_date,
    tenant_id,
    overage_gb,
    cast(overage_gb * overage_cents_per_gb as integer) as overage_cents
from rated
