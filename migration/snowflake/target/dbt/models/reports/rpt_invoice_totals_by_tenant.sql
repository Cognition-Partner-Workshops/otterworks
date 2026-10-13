-- rpt_invoice_totals_by_tenant: the dataset of source/reports/rpt_invoice_totals_by_tenant.rdl as a view. Consumers pass @BusinessDate as
-- WHERE business_date = ? and keep the report's ORDER BY.
select
    business_date,
    tenant_id,
    sum(amount_cents) as amount_cents,
    count(distinct invoice_id) as invoice_count
from {{ ref('build_invoice_lines') }}
group by business_date, tenant_id
