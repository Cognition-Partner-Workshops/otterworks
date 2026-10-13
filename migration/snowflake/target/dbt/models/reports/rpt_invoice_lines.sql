-- rpt_invoice_lines: the dataset of source/reports/rpt_invoice_lines.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    invoice_id,
    line_no,
    tenant_id,
    period_start,
    period_end,
    line_type,
    description,
    amount_cents,
    invoice_status
from {{ ref('build_invoice_lines') }}
