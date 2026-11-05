{{ config(tags=['doc_search_api']) }}
with raw as (
 select 'late-event' as event_id,'search.performed' as event_type,'account' as user_id,
 '{"query":" late   record ","result_count":"0","document_hit_ids":""}' as metadata,
 date_part(epoch_nanosecond,'2026-11-01 12:00:00'::timestamp_ntz) as occurred_at,
 '2026-11-02'::date as _snapshot_date,'2026-11-02 12:00:00'::timestamp_ntz as _exported_at,'a' as _row_hash
), events as ({{ latest_rows('raw','event_id') }}),
documents as (select null::varchar as id,null::varchar as title,false as is_deleted where false),
periods as (select '2026-11-01'::date as window_end_date),
report as ({{ search_items('events','documents','periods') }})
select 'day-late event was lost from the historical window' as failure
where (select count(*) from report where term='late record' and search_count=1 and zero_result_count=1)<>1
