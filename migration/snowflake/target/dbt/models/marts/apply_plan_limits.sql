select
    seats.business_date,
    seats.tenant_id,
    plans.seat_limit,
    case
        when plans.plan_id is null then null
        when seats.seat_count > plans.seat_limit then 1
        else 0
    end as over_limit
from {{ ref('rollup_seats') }} as seats
left join {{ ref('dim_plan') }} as plans
    on plans.plan_id = seats.plan_id
