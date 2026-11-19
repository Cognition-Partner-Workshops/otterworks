select
    cast(file_object_id as bigint) as file_object_id,
    cast(document_id as bigint) as document_id,
    {{ documents_stage_text('object_key') }} as object_key,
    cast(bytes_used as bigint) as bytes_used,
    {{ documents_stage_text('storage_class') }} as storage_class,
    cast(created_dt as date) as created_dt
from {{ source('bronze_documents', 'file_object') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
