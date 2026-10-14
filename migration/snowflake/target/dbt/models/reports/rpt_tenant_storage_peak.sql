-- rpt_tenant_storage_peak: the dataset of source/reports/rpt_tenant_storage_peak.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    tenant_id,
    tenant_name,
    plan_tier,
    storage_peak_mb,
    bytes_used
from {{ ref('build_mart_tenant_usage') }}
