select
    cast(comment_id as bigint) as comment_id,
    cast(document_id as bigint) as document_id,
    cast(user_id as bigint) as user_id,
    {{ documents_stage_text('comment_text') }} as comment_text,
    {{ documents_timestamp('created_ts') }} as created_ts
from {{ source('bronze_documents', 'doc_comment') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
