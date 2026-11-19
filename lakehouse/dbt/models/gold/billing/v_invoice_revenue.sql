select min(currency_cd) as currency_cd, date_format(invoice_dt, 'yyyy-MM') as invoice_period,
       count(*) as invoice_count, sum(total_amount) as total_amount
from {{ ref('v_invoice_base') }}
group by lower(rtrim(currency_cd)), date_format(invoice_dt, 'yyyy-MM')
