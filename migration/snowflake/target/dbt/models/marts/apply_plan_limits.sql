{{ config(
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="business_date"
) }}

select
    f.business_date,
    f.tenant_id,
    case when p.plan_id is null then null else p.seat_limit end as seat_limit,
    case
        when p.plan_id is null then null
        when f.seat_count > p.seat_limit then 1
        else 0
    end as over_limit
from {{ ref("rollup_seats") }} as f
left join {{ ref("dim_plan") }} as p
    on p.plan_id = f.plan_id
where f.business_date = {{ business_date() }}
