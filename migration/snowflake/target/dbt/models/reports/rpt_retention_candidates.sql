-- rpt_retention_candidates: the dataset of source/reports/rpt_retention_candidates.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    tenant_id,
    resource_type,
    resource_id,
    retention_action,
    days_since_update
from {{ ref('rollup_retention') }}
