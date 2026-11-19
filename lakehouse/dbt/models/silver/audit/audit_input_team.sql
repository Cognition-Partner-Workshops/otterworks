{{ config(materialized='ephemeral') }}
select
    cast(team_id as bigint) as team_id,
    cast(owner_user_id as bigint) as owner_user_id,
    {{ legacy_text('team_name', 80) }} as team_name,
    cast(created_dt as date) as created_dt
from {{ source('bronze_users', 'team') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
