{{ config(
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="business_date"
) }}

select
    {{ business_date() }} as business_date,
    a."id" as audit_id,
    a."tenant_id" as tenant_id,
    a."user_id" as user_id,
    a."action" as action,
    a."resource_type" as resource_type,
    a."resource_id" as resource_id,
    a."ip_address" as ip_address,
    a."timestamp" as event_ts_utc,
    current_timestamp() as loaded_at
from {{ source("raw", "STG_AUDIT_EVENTS") }} as a
where a."timestamp" >= {{ business_date() }}
  and a."timestamp" < dateadd(day, 1, {{ business_date() }})
