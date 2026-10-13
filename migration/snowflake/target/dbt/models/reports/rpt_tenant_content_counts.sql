-- rpt_tenant_content_counts: the dataset of source/reports/rpt_tenant_content_counts.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    tenant_id,
    tenant_name,
    document_count,
    file_count
from {{ ref('build_mart_tenant_usage') }}
