-- dbo.usp_rollup_audit: the business date's audit trail, one row per audit event (UTC day).
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='business_date') }}

select
    {{ business_date() }} as business_date,
    audit.audit_id,
    audit.tenant_id,
    audit.user_id,
    audit.action,
    audit.resource_type,
    audit.resource_id,
    audit.ip_address,
    audit.event_ts_utc,
    current_timestamp()::timestamp_ntz as loaded_at
from {{ ref('stg_audit_events') }} as audit
where audit.event_ts_utc >= {{ business_date() }}
  and audit.event_ts_utc < dateadd(day, 1, {{ business_date() }})
