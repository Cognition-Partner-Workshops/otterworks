{{ config(tags=['dq', 'dq_churn_model', 'dq_freshness']) }}
-- Spec schedule: "weekly, Monday after 00:00 UTC, scoring the ISO week that just ended" -> weekly => 8 days.
{% set max_export_age_days = 8 %}
-- RAW inputs in the churn_model dev database are SYNTHETIC pipeline exports (workloads/pipeline/pipeline.py export).
-- Every input the model joins per _export_id must have an export no older than the threshold.
with newest as (
  select 'users' as input, max(_exported_at) as newest_exported_at from {{ source('raw_churn_model', 'AUTH_USERS') }}
  union all
  select 'admin_users', max(_exported_at) from {{ source('raw_churn_model', 'ADMIN_ADMIN_USERS') }}
  union all
  select 'document_versions', max(_exported_at) from {{ source('raw_churn_model', 'DOCUMENT_DOCUMENT_VERSIONS') }}
)
select input, newest_exported_at
from newest
where newest_exported_at is null
   or newest_exported_at < dateadd(day, -{{ max_export_age_days }}, current_timestamp())
