select
    cast(plan_id as bigint) as plan_id,
    case when length(plan_code) > 200 then raise_error('staging plan_code exceeds 200 characters') else plan_code end as plan_code,
    case when length(plan_name) > 200 then raise_error('staging plan_name exceeds 200 characters') else plan_name end as plan_name,
    cast(monthly_fee as decimal(14,2)) as monthly_fee,
    case when length(currency_cd) > 200 then raise_error('staging currency_cd exceeds 200 characters') else currency_cd end as currency_cd
from {{ source('bronze_billing', 'plan_catalog') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
