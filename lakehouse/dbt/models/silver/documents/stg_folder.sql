select
    cast(folder_id as bigint) as folder_id,
    cast(owner_user_id as bigint) as owner_user_id,
    cast(customer_id as bigint) as customer_id,
    {{ documents_stage_text('folder_name') }} as folder_name,
    cast(created_dt as date) as created_dt
from {{ source('bronze_documents', 'folder') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
