{{ config(materialized='ephemeral') }}
select
    cast(activity_id as bigint) as activity_id,
    cast(user_id as bigint) as user_id,
    cast(activity_dt as date) as activity_dt,
    cast(login_count as int) as login_count,
    cast(document_count as int) as document_count
from {{ source('bronze_users', 'user_activity_daily') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
