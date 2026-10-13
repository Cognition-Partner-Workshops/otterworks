-- rpt_archived_content: the dataset of source/reports/rpt_archived_content.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    tenant_id,
    resource_type,
    retention_action,
    item_count
from {{ ref('build_mart_retention') }}
where retention_action = 'archive'
