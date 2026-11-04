{{ config(tags=['dq', 'dq_doc_search_api', 'dq_freshness']) }}

-- workloads/doc_search_api.yaml:3: schedule: daily, window ending on the previous UTC day.
{% set max_export_age_hours = 26 %}

select max(_exported_at) as latest_exported_at,
    dateadd(hour, -{{ max_export_age_hours }}, current_timestamp()) as freshness_cutoff
from {{ source('raw_doc_search_api', 'ANALYTICS_ANALYTICS_EVENTS') }}
having latest_exported_at is null or latest_exported_at < freshness_cutoff
    or latest_exported_at > current_timestamp()
