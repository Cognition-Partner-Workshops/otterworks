{{ config(
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="business_date"
) }}

select
    f.business_date,
    f.plan_tier,
    count(*) as tenant_count,
    sum(f.seat_count) as seat_count,
    sum(coalesce(l.seat_limit, 0)) as seat_limit_total,
    sum(case when l.over_limit = 1 then 1 else 0 end) as tenants_over_limit,
    round(cast(sum(f.seat_count) as number(10, 2)) / count(*), 2) as avg_seats_per_tenant
from {{ ref("rollup_seats") }} as f
left join {{ ref("apply_plan_limits") }} as l
    on l.business_date = f.business_date
   and l.tenant_id = f.tenant_id
where f.business_date = {{ business_date() }}
  and f.plan_tier is not null
group by f.business_date, f.plan_tier
