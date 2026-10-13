-- rpt_overage_charges: the dataset of source/reports/rpt_overage_charges.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    tenant_id,
    tenant_name,
    plan_tier,
    bytes_used,
    included_bytes,
    overage_gb,
    overage_cents_per_gb,
    overage_cents
from {{ ref('build_mart_overage') }}
