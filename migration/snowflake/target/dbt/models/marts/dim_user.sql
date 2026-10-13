with source_data as (
    select user_id, tenant_id, email, display_name, status, created_at
    from {{ source('raw', 'STG_AUTH_USERS') }}
)

select user_id, tenant_id, email, display_name, status, created_at
from source_data
