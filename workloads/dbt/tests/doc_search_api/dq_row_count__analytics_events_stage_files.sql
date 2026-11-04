{{ config(tags=['dq', 'dq_doc_search_api', 'dq_row_count']) }}

with staged as (
    select metadata$filename::varchar as file_name, count(*) as stage_count
    from @{{ target.database }}.RAW.POSTGRES_FILES/analytics_events/ (file_format => '{{ target.database }}.RAW.POSTGRES_CSV')
    group by 1
), landed as (
    select _file_name as file_name, count(*) as raw_count
    from {{ source('raw_doc_search_api', 'ANALYTICS_ANALYTICS_EVENTS') }} group by 1
)
select coalesce(s.file_name, r.file_name) as file_name,
    coalesce(stage_count, 0) as stage_count, coalesce(raw_count, 0) as raw_count
from staged s full outer join landed r on s.file_name = r.file_name
where coalesce(stage_count, 0) <> coalesce(raw_count, 0)
