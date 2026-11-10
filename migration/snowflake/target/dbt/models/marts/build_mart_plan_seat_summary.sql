-- The legacy column is decimal(10, 2), so the average is rounded to cents on insert.
select
    seats.business_date,
    seats.plan_tier,
    count(*) as tenant_count,
    sum(seats.seat_count) as seat_count,
    sum(coalesce(limits.seat_limit, 0)) as seat_limit_total,
    count_if(limits.over_limit = 1) as tenants_over_limit,
    round(sum(seats.seat_count) / count(*), 2)::number(10, 2) as avg_seats_per_tenant
from {{ ref('rollup_seats') }} as seats
left join {{ ref('apply_plan_limits') }} as limits
    on limits.business_date = seats.business_date
   and limits.tenant_id = seats.tenant_id
where seats.plan_tier is not null
group by seats.business_date, seats.plan_tier
