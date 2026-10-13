-- rpt_plan_mix: the dataset of source/reports/rpt_plan_mix.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    plan_tier,
    tenant_count,
    seat_count,
    seat_limit_total
from {{ ref('build_mart_plan_seat_summary') }}
