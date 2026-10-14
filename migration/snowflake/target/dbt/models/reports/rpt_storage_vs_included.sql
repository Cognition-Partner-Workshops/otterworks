-- rpt_storage_vs_included: the dataset of source/reports/rpt_storage_vs_included.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    tenant_id,
    tenant_name,
    plan_tier,
    bytes_used,
    included_bytes,
    overage_gb
from {{ ref('build_mart_overage') }}
