{{ config(tags=['dq_churn_model']) }}
{% set db = database_for('churn_model') %}
{% for table,key in [('AUTH_USERS','id'),('ADMIN_ADMIN_USERS','id'),('AUTH_USER_STATE_HISTORY','id'),('ADMIN_USER_STATE_HISTORY','id'),('DOCUMENT_DOCUMENT_VERSIONS','id')] %}
select 'uniqueness: {{ table }} key=' || coalesce({{ key }}::varchar,'NULL')
  || ' snapshot=' || coalesce(_snapshot_date::varchar,'NULL')
  || ' count=' || count(*)::varchar
  || ' row_hashes=' || coalesce(listagg(distinct _row_hash, ',') within group (order by _row_hash),'NULL') as failure
from {{ db }}.RAW.{{ table }}
where _snapshot_date is null or _snapshot_date in (
  select payload:snapshot_date::date from {{ db }}.RAW.PIPELINE_EXPORTS
)
group by _snapshot_date,{{ key }}
having count(*)>1 or {{ key }} is null or _snapshot_date is null
union all
{% endfor %}
select 'uniqueness: WEEKLY_CHURN_SCORES account=' || coalesce(account_id,'NULL')
  || ' week=' || coalesce(week_start_date::varchar,'NULL') || ' count=' || count(*)::varchar as failure
from {{ ref('weekly_churn_scores') }}
group by week_start_date,account_id
having count(*)>1 or week_start_date is null or account_id is null
{% for table,keys in [('CHURN_MODEL_RUNS',['run_id']),('CHURN_MODEL_EVALUATION',['run_id']),('CHURN_MODEL_SCORES',['run_id','account_id']),('CHURN_LEAKAGE_CHECK',['run_id','feature']),('CHURN_DOCUMENT_LABELS',['run_id','document_id']),('CHURN_RISK_REASONS',['run_id','account_id','note_id'])] %}
union all
select 'uniqueness: {{ table }} duplicate or null key' as failure
from {{ db }}.APP.{{ table }}
group by {{ keys | join(',') }}
having count(*)>1 {% for key in keys %}or {{ key }} is null {% endfor %}
{% endfor %}
