{{ config(tags=['dq', 'dq_doc_usage_dashboard', 'dq_freshness']) }}
-- spec schedule: "daily, after the 00:00 UTC export of admin-service" -> daily = 26 hours
{% set max_export_age_hours = 26 %}
select max(_exported_at) as newest_exported_at, count(*) as landed_rows
from {{ source('raw_doc_usage_dashboard', 'ADMIN_STORAGE_QUOTAS') }}
having max(_exported_at) is null
  or max(_exported_at) < dateadd(hour, -{{ max_export_age_hours }}, current_timestamp())
