{{ config(
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="business_date"
) }}

with storage_by_day as (
    select
        cast(dateadd(hour, -4, e."event_ts_utc") as date) as observation_date,
        e."tenant_id" as tenant_id,
        max(e."units") as peak_storage_mb
    from {{ source("raw", "STG_BILLING_USAGE_EVENTS") }} as e
    where e."kind" = 'storage'
      and cast(dateadd(hour, -4, e."event_ts_utc") as date)
        between dateadd(day, -27, {{ business_date() }}) and {{ business_date() }}
    group by
        cast(dateadd(hour, -4, e."event_ts_utc") as date),
        e."tenant_id"
)

select
    {{ business_date() }} as business_date,
    s.tenant_id,
    s.observation_date,
    t.plan_tier,
    s.peak_storage_mb,
    cast(s.peak_storage_mb as bigint) * 1048576 as bytes_used,
    seats.seat_count,
    cast(null as bigint) as forecast_bytes_30d,
    cast(null as timestamp_ntz) as forecast_generated_at,
    current_timestamp() as loaded_at
from storage_by_day as s
left join {{ ref("dim_tenant") }} as t
    on t.tenant_id = s.tenant_id
left join {{ ref("rollup_seats") }} as seats
    on seats.tenant_id = s.tenant_id
   and seats.business_date = {{ business_date() }}
