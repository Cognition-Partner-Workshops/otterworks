select
    cast(customer_id as bigint) as customer_id,
    cast(owner_user_id as bigint) as owner_user_id,
    case when length(account_name) > 200 then raise_error('staging account_name exceeds 200 characters') else account_name end as account_name,
    case when length(status_cd) > 200 then raise_error('staging status_cd exceeds 200 characters') else status_cd end as status_cd,
    case when length(currency_cd) > 200 then raise_error('staging currency_cd exceeds 200 characters') else currency_cd end as currency_cd,
    cast(created_dt as date) as created_dt,
    case when length(account_number) > 200 then raise_error('staging account_number exceeds 200 characters') else account_number end as account_number,
    case when length(country_cd) > 200 then raise_error('staging country_cd exceeds 200 characters') else country_cd end as country_cd,
    case when length(region_cd) > 200 then raise_error('staging region_cd exceeds 200 characters') else region_cd end as region_cd
from {{ source('bronze_billing', 'customer_account') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
