-- pkg_audit: audit_events.csv -> stg.stg_audit_events (truncate and full reload every run).
-- BusinessDate is a package parameter but nothing in the data flow reads it.
with extract as (
    select * from {{ source('pkg_audit', 'EXT_AUDIT_EVENTS') }}
),

-- LKP Tenant from user: one tenant per user, MIN(tenant_id) when a user is in several
-- workspaces; no match leaves tenant_id NULL and keeps the row.
tenant_by_user as (
    select "user_id" as user_id, min("tenant_id") as tenant_id
    from {{ source('raw', 'STG_AUTH_WORKSPACE_MEMBERS') }}
    group by "user_id"
),

-- DER Normalise timestamps: REPLACE(timestamp, "Z", "") cast to DT_DBTIMESTAMP2. The replay
-- lands microsecond precision, so the seventh fractional digit is truncated unless
-- pkg_audit_timestamp_full_precision keeps it.
typed as (
    select
        extract.*,
        to_timestamp_ntz(replace(extract."TIMESTAMP", 'Z', '')) as event_ts_raw
    from extract
)

select
    typed.id::varchar(64) as audit_id,
    tenant_by_user.tenant_id::varchar(36) as tenant_id,
    typed.user_id::varchar(36) as user_id,
    typed.action::varchar(30) as action,
    typed.resource_type::varchar(30) as resource_type,
    typed.resource_id::varchar(64) as resource_id,
    -- FF_SRC reads an empty field as NULL; RAW keeps it as ''.
    nullif(typed.details, '')::varchar(2000) as details,
    nullif(typed.ip_address, '')::varchar(45) as ip_address,
    nullif(typed.user_agent, '')::varchar(400) as user_agent,
{%- if var('pkg_audit_timestamp_full_precision', false) %}
    typed.event_ts_raw as event_ts_utc,
{%- else %}
    dateadd(
        nanosecond, -mod(date_part(nanosecond, typed.event_ts_raw), 1000), typed.event_ts_raw
    )::timestamp_ntz as event_ts_utc,
{%- endif %}
    '{{ run_started_at.strftime("%Y-%m-%d %H:%M:%S.%f") }}'::timestamp_ntz as extracted_at,
    'audit-service'::varchar(40) as source_system
from typed
left join tenant_by_user
    on typed.user_id = tenant_by_user.user_id
