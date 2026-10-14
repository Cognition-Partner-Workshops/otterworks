-- rpt_storage_growth_trend: the dataset of source/reports/rpt_storage_growth_trend.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    tenant_id,
    observation_date,
    plan_tier,
    peak_storage_mb,
    bytes_used
from {{ ref('build_capacity_forecast_input') }}
