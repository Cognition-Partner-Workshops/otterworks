-- dbo.usp_build_capacity_forecast_input: the last 28 days of storage peaks per tenant, for the
-- weekly capacity forecast. The forecast (OPS.UBW_CAPACITY_FORECAST_WEEKLY, the Snowpark port of
-- etl/scripts/capacity_forecast_weekly.py) writes forecast_bytes_30d and forecast_generated_at
-- back onto the business date rows, as the legacy job does.
--
-- Observation days use the same bucketing as rollup_storage_daily: the UTC day by default, the
-- legacy fixed DATEADD(hour, -4, ...) Eastern offset with legacy_storage_day_eastern_fixed_offset.
-- seat_count comes from the finished seat fact (apply_plan_limits), so it follows
-- legacy_seats_count_workspace_memberships.
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='business_date') }}

{%- set legacy_offset = var('legacy_storage_day_eastern_fixed_offset', false) %}

with samples as (
    select
        {% if legacy_offset -%}
        to_date(dateadd(hour, -4, event_ts_utc))
        {%- else -%}
        {{ to_business_date('event_ts_utc') }}
        {%- endif %} as observation_date,
        tenant_id,
        units
    from {{ ref('stg_billing_usage_events') }}
    where event_kind = 'storage'
),

peaks as (
    select observation_date, tenant_id, max(units) as peak_storage_mb
    from samples
    where observation_date between dateadd(day, -27, {{ business_date() }}) and {{ business_date() }}
    group by observation_date, tenant_id
)

select
    {{ business_date() }} as business_date,
    peaks.tenant_id,
    peaks.observation_date,
    tenants.plan_tier,
    peaks.peak_storage_mb,
    peaks.peak_storage_mb::number(38, 0) * 1048576 as bytes_used,
    seats.seat_count,
    null::number(38, 0) as forecast_bytes_30d,
    null::timestamp_ntz as forecast_generated_at,
    current_timestamp()::timestamp_ntz as loaded_at
from peaks
left join {{ ref('dim_tenant') }} as tenants
    on tenants.tenant_id = peaks.tenant_id
left join {{ ref('apply_plan_limits') }} as seats
    on seats.tenant_id = peaks.tenant_id
   and {{ for_business_date('seats.business_date') }}
