-- pkg_billing_usage: billing_usage_events.csv -> stg.stg_billing_usage_events.
-- The package never truncates its table: the Script Task reads the saved watermark
-- (ops.parity_watermarks, MAX(occurred_at) after the last load, 1900-01-01 when unset),
-- the data flow appends only rows with occurred_at > watermark, and an Execute SQL step
-- saves the new MAX(occurred_at). Here the incremental table is that saved state.
{{ config(
    materialized='incremental',
    incremental_strategy='append',
    on_schema_change='fail'
) }}

with extract as (
    select
        id,
        tenant_id,
        units,
        kind,
        -- DER Normalise timestamps: (DT_DBTIMESTAMP2,7)REPLACE(occurred_at,"+00","")
        replace(occurred_at, '+00', '')::timestamp_ntz as occurred_at
    from {{ source('pkg_billing_usage', 'EXT_BILLING_USAGE_EVENTS') }}
)

select
    id::varchar(36) as event_id,
    tenant_id::varchar(36) as tenant_id,
    kind::varchar(20) as event_kind,
    units::integer as units,
    occurred_at as event_ts_utc,
    occurred_at,
    -- @[System::StartTime] on the Eastern server clock
    convert_timezone('America/New_York', current_timestamp())::timestamp_ntz as extracted_at,
    'legacy-billing'::varchar(40) as source_system
from extract
{% if is_incremental() %}
where occurred_at > (
    select coalesce(max(occurred_at), '1900-01-01'::timestamp_ntz) from {{ this }}
)
{% endif %}
