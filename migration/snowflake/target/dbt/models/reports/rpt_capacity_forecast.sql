-- rpt_capacity_forecast: the dataset of source/reports/rpt_capacity_forecast.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    tenant_id,
    observation_date,
    plan_tier,
    peak_storage_mb,
    bytes_used,
    seat_count,
    forecast_bytes_30d,
    forecast_generated_at
from {{ ref('build_capacity_forecast_input') }}
