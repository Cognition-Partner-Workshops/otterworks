-- dbo.usp_rollup_usage_events: the business date's metered usage events (UTC day).
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='business_date') }}

select
    {{ business_date() }} as business_date,
    events.event_id,
    events.tenant_id,
    events.event_kind,
    events.units,
    events.event_ts_utc,
    current_timestamp()::timestamp_ntz as loaded_at
from {{ ref('stg_billing_usage_events') }} as events
where events.event_ts_utc >= {{ business_date() }}
  and events.event_ts_utc < dateadd(day, 1, {{ business_date() }})
