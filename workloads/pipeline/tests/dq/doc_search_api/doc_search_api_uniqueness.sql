{{ config(tags=['dq_doc_search_api']) }}
{% set db = database_for('doc_search_api') %}
{% for table,key in [('ANALYTICS_ANALYTICS_EVENTS','event_id'),('DOCUMENT_DOCUMENTS','id')] %}
select 'uniqueness: {{ table }} key=' || coalesce({{ key }}::varchar,'NULL')
  || ' snapshot=' || coalesce(_snapshot_date::varchar,'NULL')
  || ' count=' || count(*)::varchar
  || ' row_hashes=' || coalesce(listagg(distinct _row_hash, ',') within group (order by _row_hash),'NULL') as failure
from {{ db }}.RAW.{{ table }}
where _snapshot_date is not null and _snapshot_date in (
  select payload:snapshot_date::date from {{ db }}.RAW.PIPELINE_EXPORTS
)
group by _snapshot_date,{{ key }}
having count(*)>1 or {{ key }} is null or _snapshot_date is null
union all
{% endfor %}
select 'uniqueness: TOP_SEARCH_ITEMS account=' || coalesce(account_id,'NULL')
  || ' window=' || coalesce(window_end_date::varchar,'NULL')
  || ' item_type=' || coalesce(item_type,'NULL') || ' rank=' || coalesce(rank::varchar,'NULL')
  || ' count=' || count(*)::varchar as failure
from {{ ref('top_search_items') }}
group by window_end_date,account_id,item_type,rank
having count(*)>1 or window_end_date is null or account_id is null or item_type is null or rank is null
