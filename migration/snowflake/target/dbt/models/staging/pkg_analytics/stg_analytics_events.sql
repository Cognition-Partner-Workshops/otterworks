-- Replaces SSIS pkg_analytics: truncate + full load of analytics_events.csv into stg.stg_analytics_events.
with events as (
    select
        event_id::varchar(64) as event_id,
        event_type::varchar(64) as event_type,
        user_id::varchar(128) as user_id,
        resource_id::varchar(128) as resource_id,
        resource_type::varchar(64) as resource_type,
        metadata::varchar(2000) as metadata,
        occurred_at::number(19, 0) as occurred_at
    from {{ source('pkg_analytics', 'EXT_ANALYTICS_EVENTS') }}
),

-- LKP Tenant from user: the package's reference query, read from the landed SQL Server copy.
tenant_by_user as (
    select "user_id" as user_id, min("tenant_id") as tenant_id
    from {{ source('raw', 'STG_AUTH_WORKSPACE_MEMBERS') }}
    group by "user_id"
)

select
    events.event_id,
    events.event_type,
    events.user_id,
    events.resource_id,
    events.resource_type,
    events.metadata,
    events.occurred_at,
    -- DER: DATEADD("ss", (DT_I4)(occurred_at / 1000000000), 1970-01-01); sub-second part dropped.
    dateadd(
        second, trunc(events.occurred_at / 1000000000)::integer, '1970-01-01'::timestamp_ntz
    ) as event_ts_utc,
    -- SCR Row checksum (OPS.SSIS_PKG_ANALYTICS): SHA-256 upper hex of the five source fields.
    upper(sha2(
        events.event_id || '|' || events.event_type || '|' || events.user_id || '|'
        || events.resource_id || '|' || events.occurred_at::varchar,
        256
    ))::varchar(64) as row_checksum,
    -- Lookup no-match keeps the row with a NULL tenant_id.
    tenant_by_user.tenant_id::varchar(36) as tenant_id,
    '{{ run_started_at.strftime("%Y-%m-%d %H:%M:%S.%f") }}'::timestamp_ntz as extracted_at,
    'analytics-service'::varchar(40) as source_system
from events
left join tenant_by_user on tenant_by_user.user_id = events.user_id
