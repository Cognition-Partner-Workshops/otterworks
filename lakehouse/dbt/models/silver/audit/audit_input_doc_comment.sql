{{ config(materialized='ephemeral') }}
select
    cast(comment_id as bigint) as comment_id,
    cast(document_id as bigint) as document_id,
    cast(user_id as bigint) as user_id,
    {{ legacy_text('comment_text', 160) }} as comment_text,
    {{ audit_timestamp('created_ts') }} as created_ts
from {{ source('bronze_documents', 'doc_comment') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
