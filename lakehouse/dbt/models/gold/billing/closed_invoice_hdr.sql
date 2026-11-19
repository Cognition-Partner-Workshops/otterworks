-- depends_on: {{ ref('monthly_gl_journal_line') }}
select invoice_id, customer_id, subscription_id, invoice_dt, bill_dt, period_start_dt,
       currency_cd, total_amount, invoice_number, tax_rate_id, subtotal_amount, tax_amount,
       date_format(invoice_dt, 'yyyy-MM') as invoice_period,
       cast(date_format(period_start_dt, 'yyyyMMdd') as int) as period_key,
       date_sub(invoice_dt, 1) as prior_period_end_dt, month(invoice_dt) as invoice_month,
       case when bill_dt >= add_months(trunc(to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd'), 'MM'), -1)
                  and bill_dt < trunc(to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd'), 'MM')
            then 'Y' else period_closed_cd end as period_closed_cd, currency_control_total
from {{ ref('monthly_invoice_hdr') }}
