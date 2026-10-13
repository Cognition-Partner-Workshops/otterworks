with source_data as (
    select workspace_id, tenant_id, workspace_name, created_at
    from {{ source('raw', 'STG_AUTH_WORKSPACE_MEMBERS') }}
)

select distinct workspace_id, tenant_id, workspace_name, created_at
from source_data
