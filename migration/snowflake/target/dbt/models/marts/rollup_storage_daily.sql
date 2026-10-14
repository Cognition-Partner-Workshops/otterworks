-- dbo.usp_rollup_storage_daily: daily storage peak per tenant from the storage metering samples.
--
-- The legacy procedure buckets samples into a day with DATEADD(hour, -4, event_ts_utc): a fixed
-- US Eastern daylight offset. Every other fact (usage events, audit, invoices) uses the UTC day,
-- and the offset is an hour wrong whenever Eastern is on standard time. This model uses the UTC
-- day. Set the var legacy_storage_day_eastern_fixed_offset to true to reproduce the legacy
-- bucketing exactly while the data owners decide (see gate/out/ledger.md, rollup_storage_daily).
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='business_date') }}

{%- set legacy_offset = var('legacy_storage_day_eastern_fixed_offset', false) %}

with samples as (
    select
        {% if legacy_offset -%}
        to_date(dateadd(hour, -4, event_ts_utc))
        {%- else -%}
        {{ to_business_date('event_ts_utc') }}
        {%- endif %} as business_date,
        tenant_id,
        units
    from {{ ref('stg_billing_usage_events') }}
    where event_kind = 'storage'
),

daily as (
    select
        business_date,
        tenant_id,
        count(*) as sample_count,
        max(units) as peak_storage_mb
    from samples
    where {{ for_business_date('business_date') }}
    group by business_date, tenant_id
)

select
    daily.business_date,
    daily.tenant_id,
    tenants.plan_id,
    daily.sample_count,
    daily.peak_storage_mb,
    daily.peak_storage_mb::number(38, 0) * 1048576 as bytes_used,
    plans.included_bytes,
    current_timestamp()::timestamp_ntz as loaded_at
from daily
left join {{ ref('dim_tenant') }} as tenants
    on tenants.tenant_id = daily.tenant_id
left join {{ ref('dim_plan') }} as plans
    on plans.plan_id = tenants.plan_id
