-- rpt_seats_over_limit: the dataset of source/reports/rpt_seats_over_limit.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    tenant_id,
    plan_id,
    plan_tier,
    seat_count,
    seat_limit,
    over_limit
from {{ ref('apply_plan_limits') }}
where over_limit = 1
