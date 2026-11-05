{{ config(tags=['dq_churn_model']) }}
{% set db = database_for('churn_model') %}
with task_runs as (
  select *
  from table({{ db }}.INFORMATION_SCHEMA.TASK_HISTORY(
    TASK_NAME=>'REFRESH_CHURN_MODEL',
    SCHEDULED_TIME_RANGE_END=>CURRENT_TIMESTAMP(), RESULT_LIMIT=>10000))
  where database_name='{{ db }}' and schema_name='APP'
), successful_run as (
  select max(completed_time) as completed_time from task_runs where state='SUCCEEDED'
), latest_attempt as (
  select state from task_runs where state not in ('SCHEDULED','EXECUTING')
  qualify row_number() over (order by scheduled_time desc, attempt_number desc)=1
), latest_export as (
  select payload:snapshot_date::date as snapshot_date, payload:exported_at::timestamp_ntz as exported_at
  from {{ db }}.RAW.PIPELINE_EXPORTS
  qualify row_number() over (order by snapshot_date desc, exported_at desc)=1
)
select 'freshness: no successful refresh in the last two hours' as failure
from successful_run
where completed_time is null or completed_time<=dateadd(hour,-2,current_timestamp())
union all
select 'freshness: no source export' as failure
where not exists (select 1 from latest_export)
union all
select 'freshness: latest completed refresh attempt did not succeed' as failure
from latest_attempt where state<>'SUCCEEDED'
union all
select 'freshness: latest export has not had a successful refresh' as failure
from successful_run r cross join latest_export e
where convert_timezone('UTC',r.completed_time)::timestamp_ntz<e.exported_at
union all
select 'freshness: missing latest export completed week in output' as failure
from latest_export e
where e.snapshot_date is null or e.exported_at is null or not exists (
  select 1 from {{ ref('weekly_churn_scores') }} o
  where o.week_start_date=dateadd(day,-7,dateadd(day,1-dayofweekiso(e.snapshot_date),e.snapshot_date))
)
