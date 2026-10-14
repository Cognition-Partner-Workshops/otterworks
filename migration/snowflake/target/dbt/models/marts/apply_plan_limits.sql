-- dbo.usp_apply_plan_limits: stamps the plan seat limit on the day's seat rows and flags tenants
-- over it. The legacy procedure UPDATEs fact.fact_seat_assignments in place; this model is the
-- finished fact_seat_assignments row (rollup_seats plus the limit columns), which the seat
-- reports and the plan-tier summary read. Rows whose plan is missing keep NULL limits, as the
-- legacy UPDATE ... JOIN leaves them.
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='business_date') }}

select
    seats.business_date,
    seats.tenant_id,
    seats.plan_id,
    seats.plan_tier,
    seats.seat_count,
    plans.seat_limit,
    case
        when plans.plan_id is null then null
        when seats.seat_count > plans.seat_limit then 1
        else 0
    end as over_limit,
    current_timestamp()::timestamp_ntz as loaded_at
from {{ ref('rollup_seats') }} as seats
left join {{ ref('dim_plan') }} as plans
    on plans.plan_id = seats.plan_id
where {{ for_business_date('seats.business_date') }}
