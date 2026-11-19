select
    cast(session_id as bigint) as session_id,
    cast(document_id as bigint) as document_id,
    cast(user_id as bigint) as user_id,
    {{ documents_timestamp('start_ts') }} as start_ts,
    {{ documents_timestamp('end_ts') }} as end_ts
from {{ source('bronze_documents', 'collab_session') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
