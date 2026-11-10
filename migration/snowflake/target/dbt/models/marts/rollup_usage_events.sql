select
    {{ business_date() }} as business_date,
    "id" as event_id,
    "tenant_id" as tenant_id,
    "kind" as event_kind,
    "units" as units,
    "event_ts_utc" as event_ts_utc
from {{ source('raw', 'STG_BILLING_USAGE_EVENTS') }}
where "event_ts_utc" >= {{ business_date() }}
  and "event_ts_utc" < dateadd(day, 1, {{ business_date() }})
