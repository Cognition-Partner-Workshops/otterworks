select 
    cast(comment_id as bigint) as comment_id,
    cast(document_id as bigint) as document_id,
    cast(user_id as bigint) as user_id,
    {{ legacy_text('comment_text', 160) }} as comment_text,
    cast(created_ts as timestamp) as created_ts
from {{ ref('stg_doc_comment') }}
