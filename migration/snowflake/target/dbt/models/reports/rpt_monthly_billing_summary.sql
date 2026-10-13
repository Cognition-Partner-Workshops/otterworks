-- rpt_monthly_billing_summary: the dataset of source/reports/rpt_monthly_billing_summary.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    line_type,
    invoice_status,
    count(*) as line_count,
    sum(amount_cents) as amount_cents
from {{ ref('build_invoice_lines') }}
group by business_date, line_type, invoice_status
