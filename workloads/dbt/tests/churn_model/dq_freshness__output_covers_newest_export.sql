{{ config(tags=['dq', 'dq_churn_model', 'dq_freshness']) }}
-- Spec schedule: "weekly, Monday after 00:00 UTC, scoring the ISO week that just ended".
-- Business rule: an export scores the Monday-to-Sunday UTC week before the week it was taken in,
-- so the output's newest week_start_date must reach the week of the newest users export.
-- RAW inputs in the churn_model dev database are SYNTHETIC pipeline exports (workloads/pipeline/pipeline.py export).
with expected as (
  select max(dateadd(day, -7, date_trunc('week', convert_timezone('UTC', _exported_at)::date))::date) as expected_week
  from {{ source('raw_churn_model', 'AUTH_USERS') }}
  where _export_id is not null and _exported_at is not null
), actual as (
  select max(week_start_date) as newest_week from {{ ref('churn_model') }}
)
select e.expected_week, a.newest_week
from expected e cross join actual a
where a.newest_week is null or a.newest_week < e.expected_week
