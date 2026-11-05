{{ config(tags=['dq_doc_search_api']) }}
{% set db = database_for('doc_search_api') %}
with latest_export as (
  select payload, payload:snapshot_date::date as snapshot_date,
    payload:exported_at::timestamp_ntz as exported_at
  from {{ db }}.RAW.PIPELINE_EXPORTS
  qualify row_number() over (order by snapshot_date desc, exported_at desc)=1
), landed_events as (
  {{ latest_rows(db ~ '.RAW.ANALYTICS_ANALYTICS_EVENTS', 'event_id', true) }}
), landed_documents as (
  {{ latest_rows(db ~ '.RAW.DOCUMENT_DOCUMENTS', 'id', true) }}
), manifest_events as (
  select r.value:event_id::varchar as event_id, r.value:event_type::varchar as event_type,
    r.value:user_id::varchar as user_id, r.value:metadata::varchar as metadata,
    r.value:occurred_at::number as occurred_at
  from latest_export e, lateral flatten(input=>e.payload:tables:ANALYTICS_ANALYTICS_EVENTS) r
), manifest_documents as (
  select r.value:id::varchar as id, r.value:is_deleted::boolean as is_deleted
  from latest_export e, lateral flatten(input=>e.payload:tables:DOCUMENT_DOCUMENTS) r
)
{% for source in ['manifest','landed'] %}
, {{ source }}_windowed as (
  select t.user_id as account_id,
    regexp_replace(lower(trim(parse_json(t.metadata):query::string)), '\\s+', ' ')::varchar(500) as term,
    parse_json(t.metadata):document_hit_ids::string as hit_ids
  from {{ source }}_events t join latest_export e on
  {% if source == 'landed' %}
    t._snapshot_date=e.snapshot_date and t._exported_at=e.exported_at and
  {% endif %}
    t.event_type='search.performed'
    and to_timestamp_ntz(t.occurred_at,9)>=dateadd(day,-28,e.snapshot_date)
    and to_timestamp_ntz(t.occurred_at,9)<e.snapshot_date
), {{ source }}_term_counts as (
  select account_id, least(count(distinct term),10) as n
  from {{ source }}_windowed where term<>'' group by account_id
), {{ source }}_document_counts as (
  select w.account_id, least(count(distinct d.id),10) as n
  from {{ source }}_windowed w,
    lateral split_to_table(w.hit_ids, ',') f,
    {{ source }}_documents d,
    latest_export e
  where trim(f.value::string)=d.id and not d.is_deleted
  {% if source == 'landed' %}
    and d._snapshot_date=e.snapshot_date and d._exported_at=e.exported_at
  {% endif %}
  group by w.account_id
), {{ source }}_expected as (
  select coalesce(sum(n),0) as n from (
    select n from {{ source }}_term_counts union all select n from {{ source }}_document_counts
  )
)
{% endfor %}
, actual as (
  select count(*) as n from {{ ref('top_search_items') }}
  where window_end_date=(select dateadd(day,-1,snapshot_date) from latest_export)
)
select 'row_count: no export manifest' as failure where not exists (select 1 from latest_export)
{% for source in ['manifest','landed'] %}
union all
select 'row_count: output count differs from {{ source }} spec-derived top terms and documents' as failure
from {{ source }}_expected e cross join actual a where e.n<>a.n
{% endfor %}
{% for table,key in [('ANALYTICS_ANALYTICS_EVENTS','event_id'),('DOCUMENT_DOCUMENTS','id')] %}
union all
select 'row_count: {{ table }} manifest count differs from landed rows' as failure
from latest_export e
where array_size(e.payload:tables:{{ table }}) is null
  or array_size(e.payload:tables:{{ table }})<>(
    select count(distinct t.{{ key }}) from {{ db }}.RAW.{{ table }} t
    where t._snapshot_date=e.snapshot_date and t._exported_at=e.exported_at)
{% endfor %}
union all
select 'row_count: manifest DOCUMENT_DOCUMENTS fixture must contain 50000 documents' as failure
from latest_export where array_size(payload:tables:DOCUMENT_DOCUMENTS) is distinct from 50000
union all
select 'row_count: landed DOCUMENT_DOCUMENTS fixture must contain 50000 documents' as failure
from latest_export e where 50000<>(
  select count(distinct t.id) from {{ db }}.RAW.DOCUMENT_DOCUMENTS t
  where t._snapshot_date=e.snapshot_date and t._exported_at=e.exported_at)
union all
select 'row_count: manifest ADMIN_ADMIN_USERS fixture must contain 2000 customers' as failure
from latest_export where array_size(payload:tables:ADMIN_ADMIN_USERS) is distinct from 2000
