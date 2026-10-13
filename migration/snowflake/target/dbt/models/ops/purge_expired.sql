-- dbo.usp_purge_expired: weekly housekeeping that trims the run log, the agent history and the
-- usage and audit facts older than @retention_days (400).
--
-- The deletes run in the UBW_WEEKLY_RETENTION task (target/tasks/weekly_retention.sql). This view
-- is what survives them: the latest status of every object in the run log inside the window.
{{ config(materialized='view') }}

{%- set retention_days = var('purge_retention_days', 400) %}

select
    object_name,
    status,
    business_date,
    rows_written
from {{ ref('log_run') }}
where business_date >= dateadd(day, -{{ retention_days }}, current_date())
qualify row_number() over (partition by object_name order by business_date desc) = 1
