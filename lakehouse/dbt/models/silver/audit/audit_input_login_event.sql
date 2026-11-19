{{ config(materialized='ephemeral') }}
select
    cast(login_id as bigint) as login_id,
    cast(user_id as bigint) as user_id,
    {{ audit_timestamp('login_ts') }} as login_ts,
    {{ legacy_text('result_cd', 12, true) }} as result_cd,
    {{ legacy_text('client_type', 12, true) }} as client_type
from {{ source('bronze_users', 'login_event') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
