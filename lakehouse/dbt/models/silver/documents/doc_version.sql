with ranked as (
    select *, row_number() over (
        partition by document_id order by version_ts desc nulls first, version_id desc nulls first
    ) as version_rank
    from {{ ref('stg_doc_version') }}
)
select version_id, document_id, version_no, version_ts, file_size,
       {{ legacy_text('content_hash', 64) }} as content_hash
from ranked
where version_rank = 1
