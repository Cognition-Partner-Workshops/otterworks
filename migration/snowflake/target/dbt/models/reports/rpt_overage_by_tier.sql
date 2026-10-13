-- rpt_overage_by_tier: the dataset of source/reports/rpt_overage_by_tier.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    plan_tier,
    count(*) as tenant_count,
    sum(overage_gb) as overage_gb,
    sum(overage_cents) as overage_cents
from {{ ref('build_mart_overage') }}
group by business_date, plan_tier
