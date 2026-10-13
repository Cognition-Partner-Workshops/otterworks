-- rpt_seat_limit_headroom: the dataset of source/reports/rpt_seat_limit_headroom.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    tenant_id,
    plan_tier,
    seat_count,
    seat_limit,
    seat_limit - seat_count as seat_headroom
from {{ ref('apply_plan_limits') }}
