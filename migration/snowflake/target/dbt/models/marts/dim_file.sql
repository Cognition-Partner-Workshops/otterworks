with source_data as (
    select file_id, workspace_id, owner_user_id, file_name, size_bytes, mime_type, created_at
    from {{ source('raw', 'STG_FILES') }}
)

select file_id, workspace_id, owner_user_id, file_name, size_bytes, mime_type, created_at
from source_data
