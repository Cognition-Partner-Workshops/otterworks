with source_data as (
    select document_id, workspace_id, owner_user_id, title, status, created_at, updated_at
    from {{ source('raw', 'STG_DOCUMENTS') }}
)

select document_id, workspace_id, owner_user_id, title, status, created_at, updated_at
from source_data
