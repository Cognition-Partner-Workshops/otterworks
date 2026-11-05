{{ config(tags=['dq_doc_search_api']) }}
{% set db = database_for('doc_search_api') %}
with latest_export as (
  select payload:snapshot_date::date as snapshot_date, payload:exported_at::timestamp_ntz as exported_at
  from {{ db }}.RAW.PIPELINE_EXPORTS
  qualify row_number() over (order by snapshot_date desc, exported_at desc)=1
), documents as (
  {{ latest_rows(db ~ '.RAW.DOCUMENT_DOCUMENTS', 'id', true) }}
), latest_documents as (
  select d.* from documents d join latest_export e
    on d._snapshot_date=e.snapshot_date and d._exported_at=e.exported_at
)
select 'accepted_range: invalid search values for ' || coalesce(o.account_id,'NULL')
  || ' window=' || coalesce(o.window_end_date::varchar,'NULL')
  || ' item_type=' || coalesce(o.item_type,'NULL') || ' rank=' || coalesce(o.rank::varchar,'NULL') as failure
from {{ ref('top_search_items') }} o
where o.window_end_date is null or o.account_id is null or o.item_type is null or o.rank is null
  or o.window_days is null or o.window_days<>28 or o.item_type not in ('term','document')
  or o.rank not between 1 and 10 or o.search_count is null or o.search_count<1
  or o.last_searched_at is null
  or o.last_searched_at<dateadd(day,-27,o.window_end_date)
  or o.last_searched_at>=dateadd(day,1,o.window_end_date)
  or (o.item_type='term' and (o.term is null or trim(o.term)=''
    or o.document_id is not null or o.document_title is not null
    or o.zero_result_count is null or o.zero_result_count not between 0 and o.search_count))
  or (o.item_type='document' and (o.term is not null or o.zero_result_count is not null
    or o.document_id is null or o.document_title is null
    or not exists (select 1 from latest_documents d where d.id=o.document_id and not d.is_deleted)))
