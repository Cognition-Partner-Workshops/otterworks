select invoice_id, date_sub(invoice_dt, 1) as prior_dt, month(invoice_dt) as month_no,
       cast(date_format(period_start_dt, 'yyyyMMdd') as int) as period_key,
       date_format(invoice_dt, 'yyyy-MM') as invoice_period,
       to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd') as run_dt
from {{ ref('closed_invoice_hdr') }}
