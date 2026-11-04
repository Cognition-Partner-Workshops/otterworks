{{ config(tags=['dq', 'dq_doc_search_api', 'dq_row_count']) }}

with expected as (
    select _export_id, count(distinct id) as source_keys
    from {{ source('raw_doc_search_api', 'ANALYTICS_ANALYTICS_EVENTS') }} group by 1
), actual as (
    select _export_id, count(*) as staging_count from {{ ref('search_events') }} group by 1
)
select coalesce(e._export_id, a._export_id) as export_id,
    coalesce(source_keys, 0) as source_keys, coalesce(staging_count, 0) as staging_count
from expected e full outer join actual a on equal_null(e._export_id, a._export_id)
where coalesce(source_keys, 0) <> coalesce(staging_count, 0)
