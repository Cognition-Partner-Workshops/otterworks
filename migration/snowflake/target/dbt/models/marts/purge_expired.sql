{{
    config(
        schema="OPS",
        materialized="table",
        pre_hook=[
            "delete from "
            ~ target.database
            ~ ".OPS.ETL_RUN_LOG where CREATED_AT < DATEADD(day, -400, CURRENT_DATE())",
            "delete from "
            ~ target.database
            ~ ".MARTS.ROLLUP_USAGE_EVENTS where BUSINESS_DATE < DATEADD(day, -400, CURRENT_DATE())",
            "delete from "
            ~ target.database
            ~ ".MARTS.ROLLUP_AUDIT where BUSINESS_DATE < DATEADD(day, -400, CURRENT_DATE())",
        ],
    )
}}

with cutoff as (
    select dateadd(day, -400, current_date())::date as retention_cutoff
)

select
    'ops.etl_run_log' as object_name,
    cutoff.retention_cutoff,
    count(log.created_at) as rows_older_than_cutoff
from cutoff
left join {{ target.database }}.OPS.ETL_RUN_LOG as log
    on log.created_at < cutoff.retention_cutoff
group by cutoff.retention_cutoff

union all

select
    'ops.agent_job_history' as object_name,
    cutoff.retention_cutoff,
    count(history.scheduled_time) as rows_older_than_cutoff
from cutoff
left join {{ target.database }}.OPS.TASK_HISTORY as history
    on history.scheduled_time < cutoff.retention_cutoff
group by cutoff.retention_cutoff

union all

select
    'fact.fact_usage_events' as object_name,
    cutoff.retention_cutoff,
    count(events.business_date) as rows_older_than_cutoff
from cutoff
left join {{ ref("rollup_usage_events") }} as events
    on events.business_date < cutoff.retention_cutoff
group by cutoff.retention_cutoff

union all

select
    'fact.fact_audit_events' as object_name,
    cutoff.retention_cutoff,
    count(events.business_date) as rows_older_than_cutoff
from cutoff
left join {{ ref("rollup_audit") }} as events
    on events.business_date < cutoff.retention_cutoff
group by cutoff.retention_cutoff
