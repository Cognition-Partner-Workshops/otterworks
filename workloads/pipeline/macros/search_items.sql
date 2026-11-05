{% macro search_items(events, documents, periods) %}
with parsed_events as (
 select event_id, user_id as account_id,
  regexp_replace(lower(trim(parse_json(metadata):query::string)), '\\s+', ' ')::varchar(500) as term,
  try_to_number(parse_json(metadata):result_count::string) as result_count,
  parse_json(metadata):document_hit_ids::string as hit_ids,
  to_timestamp_ntz(occurred_at,9) as searched_at
 from {{ events }} where event_type='search.performed'
), windowed as (
 select p.window_end_date,e.* from {{ periods }} p join parsed_events e
 on e.searched_at >= dateadd(day,-27,p.window_end_date)
 and e.searched_at < dateadd(day,1,p.window_end_date)
), terms as (
 select window_end_date, account_id,'term' as item_type,term,
  null::varchar(36) as document_id, null::varchar(500) as document_title,
  count(*) as search_count,coalesce(count_if(result_count=0),0) as zero_result_count,max(searched_at) as last_searched_at
 from windowed where term<>'' group by 1,2,3,4
), appearances as (
 select distinct w.window_end_date,w.account_id,w.event_id,w.searched_at,trim(f.value::string) as document_id
 from windowed w, lateral split_to_table(w.hit_ids, ',') f
), docs as (
 select a.window_end_date,a.account_id,'document' as item_type,null::varchar(500) as term,
  d.id::varchar(36) as document_id,d.title::varchar(500) as document_title,
  count(*) as search_count,null::number(10,0) as zero_result_count,max(a.searched_at) as last_searched_at
 from appearances a join {{ documents }} d on a.document_id=d.id
 where not d.is_deleted group by 1,2,3,4,5,6
), combined as (select * from terms union all select * from docs), ranked as (
 select *,row_number() over(partition by window_end_date,account_id,item_type
 order by search_count desc,last_searched_at desc,coalesce(term,document_id) asc) as item_rank from combined
)
select window_end_date::date as window_end_date,28::number(3,0) as window_days,account_id::varchar(36) as account_id,
 item_type::varchar(8) as item_type,item_rank::number(2,0) as rank,term,document_id,document_title,
 search_count::number(10,0) as search_count,zero_result_count::number(10,0) as zero_result_count,
 last_searched_at::timestamp_ntz as last_searched_at from ranked where item_rank<=10
{% endmacro %}
