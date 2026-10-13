{{ config(
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="business_date"
) }}

select
    {{ business_date() }} as business_date,
    e."id" as event_id,
    e."tenant_id" as tenant_id,
    e."kind" as event_kind,
    e."units" as units,
    e."event_ts_utc" as event_ts_utc,
    current_timestamp() as loaded_at
from {{ source("raw", "STG_BILLING_USAGE_EVENTS") }} as e
where e."event_ts_utc" >= {{ business_date() }}
  and e."event_ts_utc" < dateadd(day, 1, {{ business_date() }})
