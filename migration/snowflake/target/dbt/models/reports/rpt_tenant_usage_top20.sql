-- rpt_tenant_usage_top20: the dataset of source/reports/rpt_tenant_usage_top20.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
-- SELECT TOP (20) ... ORDER BY bytes_used DESC, per business date.
select
    business_date,
    tenant_id,
    tenant_name,
    plan_tier,
    api_units,
    compute_units,
    storage_peak_mb,
    bytes_used
from {{ ref('build_mart_tenant_usage') }}
qualify row_number() over (partition by business_date order by bytes_used desc) <= 20
