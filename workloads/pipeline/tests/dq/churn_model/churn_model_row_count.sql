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
), retained_run_times as (
  select e.run_id,coalesce(r.started_at,try_to_timestamp_ntz(
    regexp_substr(e.run_id,'[0-9]{8}T[0-9]{6}Z'),'YYYYMMDD"T"HH24MISS"Z"')) as started_at
  from {{ db }}.APP.CHURN_MODEL_EVALUATION e
  left join {{ db }}.APP.CHURN_MODEL_RUNS r on r.run_id=e.run_id
), retained_runs as (
  select run_id,started_at,dateadd(day,1-dayofweekiso(started_at::date),started_at::date) as prediction_date
  from retained_run_times
), retained_exports as (
  select r.*, p.payload:snapshot_date::date as snapshot_date,
    p.payload:exported_at::timestamp_ntz as exported_at
  from retained_runs r join {{ db }}.RAW.PIPELINE_EXPORTS p
    on p.payload:exported_at::timestamp_ntz<=r.started_at
  qualify row_number() over (partition by r.run_id order by snapshot_date desc, exported_at desc)=1
)
{% for kind,table in [('users','AUTH_USERS'),('auth','AUTH_USER_STATE_HISTORY'),('admin','ADMIN_USER_STATE_HISTORY')] %}
, scoring_{{ kind }} as (
  select r.run_id,t.* from retained_exports r join {{ db }}.RAW.{{ table }} t
    on t._snapshot_date=r.snapshot_date and t._exported_at=r.exported_at
  qualify row_number() over (partition by r.run_id,t.id order by t._row_hash desc)=1
)
{% endfor %}
, scoring_history as (
  select run_id,user_id,min(created_at) as created_at,min(effective_at) as effective_at from (
    select run_id,user_id,created_at,effective_at from scoring_auth
    union all
    select run_id,user_id,null::timestamp_ntz as created_at,effective_at from scoring_admin
  ) group by run_id,user_id
), scoring_accounts as (
  select coalesce(u.run_id,h.run_id) as run_id,coalesce(u.id,h.user_id) as account_id,
    coalesce(u.created_at,h.created_at,h.effective_at) as created_at
  from scoring_users u full outer join scoring_history h on h.run_id=u.run_id and h.user_id=u.id
)
{% for kind in ['auth','admin'] %}
, scoring_{{ kind }}_at_prediction as (
  select s.* from scoring_{{ kind }} s join retained_exports r on r.run_id=s.run_id
  where s.effective_at<r.prediction_date
  qualify row_number() over (partition by s.run_id,s.user_id order by s.effective_at desc,s.id desc)=1
)
{% endfor %}
, expected_scores as (
  select a.run_id,a.account_id,r.prediction_date from scoring_accounts a
  join retained_exports r on r.run_id=a.run_id
  left join scoring_auth_at_prediction u on u.run_id=a.run_id and u.user_id=a.account_id
  left join scoring_admin_at_prediction s on s.run_id=a.run_id and s.user_id=a.account_id
  where a.created_at<dateadd(day,-28,r.prediction_date)
    and not coalesce(u.is_deleted,false) and coalesce(s.status,'active') not in ('suspended','deleted')
), actual_scores as (
  select run_id,account_id,prediction_date,count(*) as n from {{ db }}.APP.CHURN_MODEL_SCORES
  group by run_id,account_id,prediction_date
)
select 'row_count: no export manifest' as failure where not exists (select 1 from latest_export)
union all
select 'row_count: retained scoring cohort cannot be reconstructed run=' || r.run_id
  || '; requires the source export retained from before the evaluated run' as failure
from retained_runs r where not exists (select 1 from retained_exports e where e.run_id=r.run_id)
union all
select 'row_count: retained model scores are empty for evaluated run=' || r.run_id as failure
from retained_runs r where not exists (select 1 from actual_scores s where s.run_id=r.run_id)
union all
select 'row_count: retained scoring cohort mismatch run=' || coalesce(e.run_id,a.run_id,'NULL')
  || ' account=' || coalesce(e.account_id,a.account_id,'NULL')
  || '; expected exactly one prediction for each eligible account at its evaluated run date' as failure
from expected_scores e full outer join actual_scores a
  on a.run_id=e.run_id and a.account_id=e.account_id and a.prediction_date=e.prediction_date
where e.run_id is null or a.run_id is null or a.n<>1
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
