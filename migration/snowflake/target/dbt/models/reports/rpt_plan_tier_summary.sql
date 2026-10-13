-- rpt_plan_tier_summary: the dataset of source/reports/rpt_plan_tier_summary.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
-- The RDL filters plan_tier = @PlanTier with title-case parameter values (Starter, Growth, Scale)
-- against lower-case data and relies on SQL Server's case-insensitive collation to match.
-- plan_tier carries an en-ci collation here so `plan_tier = 'Growth'` matches the same rows.
select
    business_date,
    collate(plan_tier, 'en-ci') as plan_tier,
    tenant_count,
    seat_count,
    seat_limit_total,
    tenants_over_limit,
    avg_seats_per_tenant
from {{ ref('build_mart_plan_seat_summary') }}
