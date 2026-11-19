select
    cast(document_id as bigint) as document_id,
    cast(folder_id as bigint) as folder_id,
    cast(owner_user_id as bigint) as owner_user_id,
    cast(customer_id as bigint) as customer_id,
    {{ documents_stage_text('document_name') }} as document_name,
    cast(created_dt as date) as created_dt,
    {{ documents_stage_text('status_cd') }} as status_cd,
    {{ documents_stage_text('file_type') }} as file_type
from {{ source('bronze_documents', 'document') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
