-- rpt_tenant_usage_daily: the dataset of source/reports/rpt_tenant_usage_daily.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    tenant_id,
    tenant_name,
    plan_tier,
    region_code,
    api_units,
    compute_units,
    storage_peak_mb,
    bytes_used,
    active_users,
    document_count,
    file_count
from {{ ref('build_mart_tenant_usage') }}
