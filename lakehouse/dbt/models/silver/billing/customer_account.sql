select
    cast(customer_id as bigint) as customer_id,
    cast(owner_user_id as bigint) as owner_user_id,
    {{ legacy_text('account_name', 100) }} as account_name,
    {{ legacy_text('status_cd', 12, true) }} as status_cd,
    {{ legacy_text('currency_cd', 3, true) }} as currency_cd,
    cast(created_dt as date) as created_dt,
    {{ legacy_text('account_number', 24) }} as account_number,
    {{ legacy_text('country_cd', 2, true) }} as country_cd,
    {{ legacy_text('region_cd', 20) }} as region_cd
from {{ source('bronze_billing', 'customer_account') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
