{{ config(tags=['dq_churn_model']) }}
{% set db = database_for('churn_model') %}
with successful_run as (
  select max(completed_time) as completed_time
  from table({{ db }}.INFORMATION_SCHEMA.TASK_HISTORY(
    TASK_NAME=>'REFRESH_CHURN_MODEL',
    SCHEDULED_TIME_RANGE_END=>CURRENT_TIMESTAMP(), RESULT_LIMIT=>10000))
  where state='SUCCEEDED' and database_name='{{ db }}' and schema_name='APP'
), latest_export as (
  select max(payload:snapshot_date::date) as snapshot_date from {{ db }}.RAW.PIPELINE_EXPORTS
)
select 'freshness: no successful refresh in the last two hours' as failure
from successful_run
where completed_time is null or completed_time<=dateadd(hour,-2,current_timestamp())
union all
select 'freshness: missing latest export completed week in output' as failure
from latest_export e
where e.snapshot_date is null or not exists (
  select 1 from {{ ref('weekly_churn_scores') }} o
  where o.week_start_date=dateadd(day,-7,dateadd(day,1-dayofweekiso(e.snapshot_date),e.snapshot_date))
)
