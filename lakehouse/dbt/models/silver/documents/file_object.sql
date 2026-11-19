select 
    cast(file_object_id as bigint) as file_object_id,
    cast(document_id as bigint) as document_id,
    {{ legacy_text('object_key', 160) }} as object_key,
    cast(bytes_used as bigint) as bytes_used,
    {{ legacy_text('storage_class', 12, true) }} as storage_class,
    cast(created_dt as date) as created_dt
from {{ ref('stg_file_object') }}
