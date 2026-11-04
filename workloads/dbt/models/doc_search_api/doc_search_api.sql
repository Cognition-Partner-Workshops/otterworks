{{ config(materialized='incremental', incremental_strategy='append',
    pre_hook="{{ clear_changed_dates('search_events','window_end_date') }}", post_hook="{{ output_grants() }}") }}

with batches as (
 {{ latest_batches(ref('search_events'), "dateadd(day,-1,convert_timezone('UTC', _exported_at)::date)::date") }}
), events as (
 select b.snapshot_date as window_end_date,e.user_id,e.id,
 lower(trim(regexp_replace(parse_json(e.metadata):query::varchar,'\\s+',' '))) as term,
 parse_json(e.metadata):result_count::integer as result_count,
 parse_json(e.metadata):document_hit_ids::varchar as hit_ids,
 to_timestamp_ntz(e.occurred_at,9) as searched_at,e._export_id
 from batches b join {{ ref('search_events') }} e on b._export_id=e._export_id
 where e.event_type='search.performed' and e.user_id<>''
 and to_timestamp_ntz(e.occurred_at,9)::date between dateadd(day,-27,b.snapshot_date) and b.snapshot_date
 and term not in ('','*')
), terms as (
 select window_end_date,user_id,'term' as item_type,term,null::varchar(36) as document_id,
 null::varchar(500) as document_title,count(*) as search_count,
 count_if(result_count=0) as zero_result_count,max(searched_at) as last_searched_at
 from events group by window_end_date,user_id,term
), expanded_hits as (
 select e.*,trim(h.value) as hit_id
 from events e, lateral split_to_table(e.hit_ids,',') h
), hits as (
 select distinct e.window_end_date,e.user_id,e.id,e.searched_at,d.id as document_id,d.title
 from expanded_hits e
 join {{ ref('search_documents') }} d on d.id=e.hit_id and d._export_id=e._export_id
 where not d.is_deleted
), documents as (
 select window_end_date,user_id,'document' as item_type,null::varchar(500) as term,
 document_id,title as document_title,count(*) as search_count,null::number as zero_result_count,
 max(searched_at) as last_searched_at
 from hits group by window_end_date,user_id,document_id,title
), items as (
 select * from terms union all select * from documents
)
select window_end_date::date as window_end_date,28::number(3,0) as window_days,
 user_id::varchar(36) as account_id,item_type::varchar(8) as item_type,
 row_number() over(partition by window_end_date,user_id,item_type order by search_count desc,last_searched_at desc,coalesce(term,document_id))::number(2,0) as rank,
 term::varchar(500) as term,document_id::varchar(36) as document_id,document_title::varchar(500) as document_title,
 search_count::number(10,0) as search_count,zero_result_count::number(10,0) as zero_result_count,
 last_searched_at::timestamp_ntz as last_searched_at
from items qualify rank<=10
