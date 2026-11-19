{{ config(materialized='ephemeral') }}
select
    cast(profile_id as bigint) as profile_id,
    cast(user_id as bigint) as user_id,
    {{ legacy_text('title', 60) }} as title,
    {{ legacy_text('country_cd', 2, true) }} as country_cd,
    {{ legacy_text('timezone', 40) }} as timezone
from {{ source('bronze_users', 'user_profile') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
