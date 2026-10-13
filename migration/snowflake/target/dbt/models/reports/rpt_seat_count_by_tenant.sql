-- rpt_seat_count_by_tenant: the dataset of source/reports/rpt_seat_count_by_tenant.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    tenant_id,
    plan_tier,
    seat_count,
    seat_limit
from {{ ref('apply_plan_limits') }}
