{{ config(tags=['doc_search_api']) }}
with events as (
 select 'event' as event_id, 'account' as user_id, 'search.performed' as event_type,
 '{"query":"successful","result_count":"1","document_hit_ids":""}' as metadata,
 date_part(epoch_nanosecond,'2026-11-01 12:00:00'::timestamp_ntz) as occurred_at
), documents as (select null::varchar as id,null::varchar as title,false as is_deleted where false),
periods as (select '2026-11-01'::date as window_end_date),
report as ({{ search_items('events','documents','periods') }})
select 'successful searches require numeric zero, not NULL' as failure
where (select count(*) from report where item_type='term' and search_count=1 and zero_result_count=0)<>1
