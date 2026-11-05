{{ config(tags=['dq_doc_usage_dashboard']) }}
{% set db = database_for('doc_usage_dashboard') %}
with latest_export as (
  select payload, payload:snapshot_date::date as snapshot_date,
    payload:exported_at::timestamp_ntz as exported_at
  from {{ db }}.RAW.PIPELINE_EXPORTS
  qualify row_number() over (order by snapshot_date desc, exported_at desc)=1
), quotas as (
  {{ latest_rows(db ~ '.RAW.ADMIN_STORAGE_QUOTAS', 'user_id', true) }}
), accounts as (
  {{ latest_rows(db ~ '.RAW.ADMIN_ADMIN_USERS', 'id', true) }}
), manifest_accounts as (
  select r.value:id::varchar as id, r.value:status::varchar as status
  from latest_export e, lateral flatten(input=>e.payload:tables:ADMIN_ADMIN_USERS) r
), manifest_quotas as (
  select r.value:user_id::varchar as user_id
  from latest_export e, lateral flatten(input=>e.payload:tables:ADMIN_STORAGE_QUOTAS) r
), manifest_expected as (
  select count(distinct q.user_id) as n
  from manifest_quotas q join manifest_accounts a on q.user_id=a.id
  where a.status<>'deleted'
), expected as (
  select count(distinct q.user_id) as n from quotas q join accounts a
    on q.user_id=a.id and q._snapshot_date=a._snapshot_date
  join latest_export e on q._snapshot_date=e.snapshot_date
    and q._exported_at=e.exported_at and a._exported_at=e.exported_at
  where a.status<>'deleted'
)
select 'row_count: no export manifest' as failure where not exists (select 1 from latest_export)
union all
select 'row_count: output count differs from eligible distinct quota accounts' as failure
from expected where n<>(select count(*) from {{ ref('account_storage_usage') }}
  where snapshot_date=(select snapshot_date from latest_export))
union all
select 'row_count: output count differs from manifest eligible accounts' as failure
from manifest_expected where n<>(select count(*) from {{ ref('account_storage_usage') }}
  where snapshot_date=(select snapshot_date from latest_export))
{% for table,key in [('ADMIN_STORAGE_QUOTAS','user_id'),('ADMIN_ADMIN_USERS','id'),('DOCUMENT_DOCUMENTS','id')] %}
union all
select 'row_count: {{ table }} manifest count differs from landed rows' as failure
from latest_export e
where array_size(e.payload:tables:{{ table }}) is null
  or array_size(e.payload:tables:{{ table }})<>(
    select count(distinct t.{{ key }}) from {{ db }}.RAW.{{ table }} t
    where t._snapshot_date=e.snapshot_date and t._exported_at=e.exported_at)
{% endfor %}
