-- Staging for pkg_billing_usage: RAW.STG_BILLING_USAGE_EVENTS is the SSIS landing table as loaded.
select
    "id"::varchar as event_id,
    "tenant_id"::varchar as tenant_id,
    "kind"::varchar as event_kind,
    "units"::integer as units,
    "event_ts_utc"::timestamp_ntz as event_ts_utc,
    "occurred_at"::timestamp_ntz as occurred_at,
    "extracted_at"::timestamp_ntz as extracted_at,
    "source_system"::varchar as source_system
from {{ source('raw', 'STG_BILLING_USAGE_EVENTS') }}
