-- Staging for pkg_audit: RAW.STG_AUDIT_EVENTS is the SSIS landing table as loaded.
select
    "id"::varchar as audit_id,
    "tenant_id"::varchar as tenant_id,
    "user_id"::varchar as user_id,
    "action"::varchar as action,
    "resource_type"::varchar as resource_type,
    "resource_id"::varchar as resource_id,
    "ip_address"::varchar as ip_address,
    "timestamp"::timestamp_ntz as event_ts_utc,
    "extracted_at"::timestamp_ntz as extracted_at,
    "source_system"::varchar as source_system
from {{ source('raw', 'STG_AUDIT_EVENTS') }}
