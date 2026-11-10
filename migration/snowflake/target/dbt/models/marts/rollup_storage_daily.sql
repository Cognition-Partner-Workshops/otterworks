with samples as (
    select
        dateadd(hour, -4, "event_ts_utc")::date as business_date,
        "tenant_id" as tenant_id,
        count(*) as sample_count,
        max("units") as peak_storage_mb
    from {{ source('raw', 'STG_BILLING_USAGE_EVENTS') }}
    where "kind" = 'storage'
      and dateadd(hour, -4, "event_ts_utc")::date = {{ business_date() }}
    group by 1, 2
)

select
    samples.business_date,
    samples.tenant_id,
    tenants.plan_id,
    samples.sample_count,
    samples.peak_storage_mb,
    samples.peak_storage_mb::bigint * 1048576 as bytes_used,
    plans.included_bytes
from samples
left join {{ ref('dim_tenant') }} as tenants
    on tenants.tenant_id = samples.tenant_id
left join {{ ref('dim_plan') }} as plans
    on plans.plan_id = tenants.plan_id
