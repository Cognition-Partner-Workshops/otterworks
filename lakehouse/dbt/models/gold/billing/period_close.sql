select min(currency_cd) as currency_cd, count(*) as invoice_count, sum(total_amount) as total_amount
from {{ ref('closed_invoice_hdr') }}
where bill_dt >= add_months(trunc(to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd'), 'MM'), -1)
  and bill_dt < trunc(to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd'), 'MM')
group by lower(rtrim(currency_cd))
