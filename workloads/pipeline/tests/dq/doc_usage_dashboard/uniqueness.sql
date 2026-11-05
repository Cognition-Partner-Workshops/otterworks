{{ config(tags=['dq_doc_usage_dashboard']) }}
{% set db = database_for('doc_usage_dashboard') %}
{% for table,key in [('ADMIN_STORAGE_QUOTAS','user_id'),('ADMIN_ADMIN_USERS','id'),('DOCUMENT_DOCUMENTS','id')] %}
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
select 'uniqueness: ACCOUNT_STORAGE_USAGE key=' || coalesce(account_id,'NULL')
  || ' snapshot=' || coalesce(snapshot_date::varchar,'NULL')
  || ' count=' || count(*)::varchar as failure
from {{ ref('account_storage_usage') }}
group by snapshot_date,account_id
having count(*)>1 or account_id is null or snapshot_date is null
