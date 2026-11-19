select
    cast(gl_account_id as bigint) as gl_account_id,
    case when length(account_number) > 200 then raise_error('staging account_number exceeds 200 characters') else account_number end as account_number,
    case when length(account_name) > 200 then raise_error('staging account_name exceeds 200 characters') else account_name end as account_name,
    case when length(account_type) > 200 then raise_error('staging account_type exceeds 200 characters') else account_type end as account_type,
    case when length(normal_balance) > 200 then raise_error('staging normal_balance exceeds 200 characters') else normal_balance end as normal_balance
from {{ source('bronze_billing', 'gl_account') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
