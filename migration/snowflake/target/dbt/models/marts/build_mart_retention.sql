select
    business_date,
    tenant_id,
    resource_type,
    retention_action,
    count(*) as item_count
from {{ ref('rollup_retention') }}
group by business_date, tenant_id, resource_type, retention_action
