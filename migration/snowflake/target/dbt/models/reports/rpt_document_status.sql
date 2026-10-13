-- rpt_document_status: the dataset of source/reports/rpt_document_status.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    tenant_id,
    workspace_id,
    status_label,
    document_count,
    word_count
from {{ ref('rollup_document_status') }}
