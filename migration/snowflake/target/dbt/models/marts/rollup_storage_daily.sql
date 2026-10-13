{{ config(
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="business_date"
) }}

with storage_daily as (
    select
        cast(dateadd(hour, -4, e."event_ts_utc") as date) as business_date,
        e."tenant_id" as tenant_id,
        count(*) as sample_count,
        max(e."units") as peak_storage_mb
    from {{ source("raw", "STG_BILLING_USAGE_EVENTS") }} as e
    where e."kind" = 'storage'
      and cast(dateadd(hour, -4, e."event_ts_utc") as date) = {{ business_date() }}
    group by
        cast(dateadd(hour, -4, e."event_ts_utc") as date),
        e."tenant_id"
)

select
    s.business_date,
    s.tenant_id,
    t.plan_id,
    s.sample_count,
    s.peak_storage_mb,
    cast(s.peak_storage_mb as bigint) * 1048576 as bytes_used,
    p.included_bytes,
    cast(null as integer) as overage_gb,
    cast(null as integer) as overage_cents,
    current_timestamp() as loaded_at
from storage_daily as s
left join {{ ref("dim_tenant") }} as t
    on t.tenant_id = s.tenant_id
left join {{ ref("dim_plan") }} as p
    on p.plan_id = t.plan_id
