{{ config(tags=['dq_churn_model']) }}
{% set db = database_for('churn_model') %}
with latest_export as (
  select payload, payload:snapshot_date::date as snapshot_date,
    payload:exported_at::timestamp_ntz as exported_at,
    dateadd(day,-7,dateadd(day,1-dayofweekiso(snapshot_date),snapshot_date))::date as week_start_date
  from {{ db }}.RAW.PIPELINE_EXPORTS
  qualify row_number() over (order by snapshot_date desc, exported_at desc)=1
), manifest_users as (
  select r.value:id::number as id, r.value:user_id::varchar as user_id,
    r.value:effective_at::timestamp_ntz as effective_at, r.value:created_at::timestamp_ntz as created_at,
    r.value:is_deleted::boolean as is_deleted
  from latest_export e, lateral flatten(input=>e.payload:tables:AUTH_USER_STATE_HISTORY) r
), manifest_status as (
  select r.value:id::number as id, r.value:user_id::varchar as user_id,
    r.value:effective_at::timestamp_ntz as effective_at, r.value:status::varchar as status
  from latest_export e, lateral flatten(input=>e.payload:tables:ADMIN_USER_STATE_HISTORY) r
)
{% for kind,table in [('users','AUTH_USER_STATE_HISTORY'),('status','ADMIN_USER_STATE_HISTORY')] %}
, landed_{{ kind }} as (
  select t.* from {{ db }}.RAW.{{ table }} t join latest_export e
    on t._snapshot_date=e.snapshot_date and t._exported_at=e.exported_at
  qualify row_number() over (partition by t.id order by t._row_hash desc)=1
)
{% endfor %}
{% for source in ['manifest','landed'] %}
, {{ source }}_users_at_end as (
  select u.* from {{ source }}_users u cross join latest_export e
  where u.effective_at<dateadd(day,7,e.week_start_date)
  qualify row_number() over (partition by u.user_id order by u.effective_at desc,u.id desc)=1
), {{ source }}_status_at_end as (
  select s.* from {{ source }}_status s cross join latest_export e
  where s.effective_at<dateadd(day,7,e.week_start_date)
  qualify row_number() over (partition by s.user_id order by s.effective_at desc,s.id desc)=1
), {{ source }}_expected as (
  select count(*) as n from {{ source }}_users_at_end u
  left join {{ source }}_status_at_end s on s.user_id=u.user_id
  cross join latest_export e
  where not coalesce(u.is_deleted,false) and coalesce(s.status,'active')<>'deleted'
    and u.created_at<=dateadd(day,-28,e.week_start_date)
)
{% endfor %}
, actual as (
  select count(*) as n from {{ ref('weekly_churn_scores') }}
  where week_start_date=(select week_start_date from latest_export)
)
select 'row_count: no export manifest' as failure where not exists (select 1 from latest_export)
{% for source in ['manifest','landed'] %}
union all
select 'row_count: {{ source }} eligible accounts expected=' || e.n::varchar || ' actual=' || a.n::varchar
  || '; requires authoritative source history before completed-week cutoff' as failure
from {{ source }}_expected e cross join actual a where e.n<>a.n
{% endfor %}
{% for table,key in [('AUTH_USERS','id'),('ADMIN_ADMIN_USERS','id'),('AUTH_USER_STATE_HISTORY','id'),('ADMIN_USER_STATE_HISTORY','id'),('DOCUMENT_DOCUMENT_VERSIONS','id'),('DOCUMENT_DOCUMENTS','id')] %}
union all
select 'row_count: {{ table }} manifest count differs from landed rows' as failure
from latest_export e
where array_size(e.payload:tables:{{ table }}) is null
  or array_size(e.payload:tables:{{ table }})<>(
    select count(distinct t.{{ key }}) from {{ db }}.RAW.{{ table }} t
    where t._snapshot_date=e.snapshot_date and t._exported_at=e.exported_at)
{% endfor %}
{% for table,n in [('AUTH_USERS',2000),('ADMIN_ADMIN_USERS',2000),('DOCUMENT_DOCUMENTS',50000)] %}
union all
select 'row_count: {{ table }} fixture must contain {{ n }} rows' as failure
from latest_export e
where array_size(e.payload:tables:{{ table }}) is distinct from {{ n }}
  or {{ n }}<>(select count(distinct t.id) from {{ db }}.RAW.{{ table }} t
    where t._snapshot_date=e.snapshot_date and t._exported_at=e.exported_at)
{% endfor %}
