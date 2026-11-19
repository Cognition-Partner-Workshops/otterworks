select
    cast(subscription_id as bigint) as subscription_id,
    cast(customer_id as bigint) as customer_id,
    case when length(plan_code) > 200 then raise_error('staging plan_code exceeds 200 characters') else plan_code end as plan_code,
    cast(start_dt as date) as start_dt,
    cast(end_dt as date) as end_dt,
    case when length(status_cd) > 200 then raise_error('staging status_cd exceeds 200 characters') else status_cd end as status_cd
from {{ source('bronze_billing', 'subscription') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
