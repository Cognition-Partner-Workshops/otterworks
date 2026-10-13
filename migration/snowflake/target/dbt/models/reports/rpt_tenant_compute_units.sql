-- rpt_tenant_compute_units: the dataset of source/reports/rpt_tenant_compute_units.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    tenant_id,
    tenant_name,
    plan_tier,
    compute_units
from {{ ref('build_mart_tenant_usage') }}
