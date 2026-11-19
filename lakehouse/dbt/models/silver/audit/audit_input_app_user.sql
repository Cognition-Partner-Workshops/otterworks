{{ config(materialized='ephemeral') }}
select
    cast(user_id as bigint) as user_id,
    {{ legacy_text('display_name', 60) }} as display_name,
    {{ legacy_text('email', 120) }} as email,
    {{ legacy_text('status_cd', 12, true) }} as status_cd,
    cast(created_dt as date) as created_dt
from {{ source('bronze_users', 'app_user') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
