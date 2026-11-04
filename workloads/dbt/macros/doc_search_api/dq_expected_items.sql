{% macro dq_doc_search_api_expected_items() %}
-- Independent RAW reconciliation of the spec's daily 28-day, top-10 business rule.
with source_events as (
    select * from {{ source('raw_doc_search_api', 'ANALYTICS_ANALYTICS_EVENTS') }}
    qualify row_number() over (
        partition by _export_id, id
        order by _loaded_at desc, _file_name desc, _file_row_number desc
    ) = 1
), exports as (
    select _export_id, dateadd(day, -1, convert_timezone('UTC', _exported_at)::date)::date as window_end_date
    from source_events
    where _exported_at is not null
    qualify row_number() over (
        partition by window_end_date order by _exported_at desc, _export_id desc
    ) = 1
), eligible_events as (
    select x.window_end_date, e._export_id, e.id, e.user_id as account_id,
        lower(trim(regexp_replace(parse_json(e.metadata):query::varchar, '\\s+', ' '))) as term,
        parse_json(e.metadata):result_count::integer as result_count,
        parse_json(e.metadata):document_hit_ids::varchar as document_hit_ids,
        to_timestamp_ntz(e.occurred_at, 9) as searched_at
    from source_events e join exports x on e._export_id = x._export_id
    where e.event_type = 'search.performed' and e.user_id <> ''
        and searched_at::date between dateadd(day, -27, x.window_end_date) and x.window_end_date
        and term not in ('', '*')
), source_documents as (
    select * from {{ source('raw_doc_search_api', 'DOCUMENT_DOCUMENTS') }}
    qualify row_number() over (
        partition by _export_id, id
        order by _loaded_at desc, _file_name desc, _file_row_number desc
    ) = 1
), document_searches as (
    select distinct e.window_end_date, e.account_id, e.id, e.searched_at,
        d.id as document_id, d.title as document_title
    from eligible_events e,
        lateral split_to_table(e.document_hit_ids, ',') hit,
        source_documents d
    where trim(hit.value) = d.id and e._export_id = d._export_id and not d.is_deleted
), items as (
    select window_end_date, account_id, 'term' as item_type, term,
        null::varchar as document_id, null::varchar as document_title,
        count(*) as search_count, count_if(result_count = 0) as zero_result_count,
        max(searched_at) as last_searched_at
    from eligible_events group by window_end_date, account_id, term
    union all
    select window_end_date, account_id, 'document', null::varchar,
        document_id, document_title, count(*), null::number, max(searched_at)
    from document_searches group by window_end_date, account_id, document_id, document_title
)
select *, row_number() over (
    partition by window_end_date, account_id, item_type
    order by search_count desc, last_searched_at desc, coalesce(term, document_id)
) as rank
from items qualify rank <= 10
{% endmacro %}
