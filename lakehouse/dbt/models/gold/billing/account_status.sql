select to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd') as business_dt,
       min(status_cd) as status_cd, min(currency_cd) as currency_cd, count(*) as account_count
from {{ ref('customer_account_hist') }}
where valid_from_dt <= to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
  and valid_to_dt > to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
group by lower(rtrim(status_cd)), lower(rtrim(currency_cd))
