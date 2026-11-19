select
    cast(index_log_id as bigint) as index_log_id,
    cast(document_id as bigint) as document_id,
    {{ documents_timestamp('indexed_ts') }} as indexed_ts,
    {{ documents_stage_text('status_cd') }} as status_cd,
    cast(token_count as int) as token_count
from {{ source('bronze_documents', 'search_index_log') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
