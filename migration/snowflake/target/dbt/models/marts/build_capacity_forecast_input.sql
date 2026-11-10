with peaks as (
    select
        dateadd(hour, -4, "event_ts_utc")::date as observation_date,
        "tenant_id" as tenant_id,
        max("units") as peak_storage_mb
    from {{ source('raw', 'STG_BILLING_USAGE_EVENTS') }}
    where "kind" = 'storage'
      and dateadd(hour, -4, "event_ts_utc")::date
          between dateadd(day, -27, {{ business_date() }}) and {{ business_date() }}
    group by 1, 2
)

select
    {{ business_date() }} as business_date,
    peaks.tenant_id,
    peaks.observation_date,
    tenants.plan_tier,
    peaks.peak_storage_mb,
    peaks.peak_storage_mb::bigint * 1048576 as bytes_used,
    seats.seat_count
from peaks
left join {{ ref('dim_tenant') }} as tenants
    on tenants.tenant_id = peaks.tenant_id
left join {{ ref('rollup_seats') }} as seats
    on seats.tenant_id = peaks.tenant_id
