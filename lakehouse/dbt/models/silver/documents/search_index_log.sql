{{ config(materialized='incremental', incremental_strategy='append') }}

select
    cast(index_log_id as bigint) as index_log_id,
    cast(document_id as bigint) as document_id,
    cast(indexed_ts as timestamp) as indexed_ts,
    {{ legacy_text('status_cd', 12, true) }} as status_cd,
    cast(token_count as int) as token_count
from {{ ref('stg_search_index_log') }}
where false
