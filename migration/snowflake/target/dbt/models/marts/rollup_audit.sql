select
    {{ business_date() }} as business_date,
    "id" as audit_id,
    "tenant_id" as tenant_id,
    "user_id" as user_id,
    "action" as action,
    "resource_type" as resource_type,
    "resource_id" as resource_id,
    "ip_address" as ip_address,
    "timestamp" as event_ts_utc
from {{ source('raw', 'STG_AUDIT_EVENTS') }}
where "timestamp" >= {{ business_date() }}
  and "timestamp" < dateadd(day, 1, {{ business_date() }})
