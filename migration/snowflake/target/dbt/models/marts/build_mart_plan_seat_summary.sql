-- dbo.usp_build_mart_plan_seat_summary: seats and seat limits rolled up by plan tier.
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='business_date') }}

select
    {{ business_date() }} as business_date,
    seats.plan_tier,
    count(*) as tenant_count,
    sum(seats.seat_count) as seat_count,
    sum(coalesce(seats.seat_limit, 0)) as seat_limit_total,
    sum(iff(seats.over_limit = 1, 1, 0)) as tenants_over_limit,
    -- CAST(SUM(seat_count) AS decimal(10, 2)) / COUNT(*), stored in a decimal(10, 2) column
    round(sum(seats.seat_count)::number(10, 2) / count(*), 2)::number(10, 2) as avg_seats_per_tenant,
    current_timestamp()::timestamp_ntz as loaded_at
from {{ ref('apply_plan_limits') }} as seats
where {{ for_business_date('seats.business_date') }}
  and seats.plan_tier is not null
group by seats.plan_tier
