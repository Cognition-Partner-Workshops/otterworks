{{ config(materialized='ephemeral') }}
select
    cast(identity_id as bigint) as identity_id,
    cast(user_id as bigint) as user_id,
    {{ legacy_text('provider_cd', 12, true) }} as provider_cd,
    {{ legacy_text('subject_id', 100) }} as subject_id,
    cast(created_dt as date) as created_dt
from {{ source('bronze_users', 'sso_identity') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
