{{ config(tags=['doc_search_api', 'dq_doc_search_api']) }}
with expected as (
 select column1::date as window_end_date,28::number(3,0) as window_days,
 '00000000-0000-4000-8000-000000000101'::varchar(36) as account_id,
 column2::varchar(8) as item_type,column3::number(2,0) as rank,column4::varchar(500) as term,
 column5::varchar(36) as document_id,column6::varchar(500) as document_title,column7::number(10,0) as search_count,
 column8::number(10,0) as zero_result_count,column9::timestamp_ntz as last_searched_at from values
 ('2026-11-01','term',1,'quarterly report',null,null,2,0,'2026-10-25 09:00:00'),
 ('2026-11-01','term',2,'budget',null,null,1,1,'2026-10-30 15:00:00'),
 ('2026-11-01','document',1,null,'03ebe472-1e21-9b1c-20c5-18a0d26cbe6f','Synthetic document 1',2,null,'2026-10-25 09:00:00')
), actual as (
 select * from {{ ref('top_search_items') }} where window_end_date='2026-11-01' and account_id='00000000-0000-4000-8000-000000000101'
)
select 'worked_example: unexpected or mismatched row' as failure, diff.*
from (select * from actual minus select * from expected) diff
union all
select 'worked_example: missing or mismatched row' as failure, diff.*
from (select * from expected minus select * from actual) diff
