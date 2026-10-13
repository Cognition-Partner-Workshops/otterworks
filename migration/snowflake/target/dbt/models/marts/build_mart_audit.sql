-- dbo.usp_build_mart_audit: audit events counted per tenant, action and resource type for the day.
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='business_date') }}

select
    {{ business_date() }} as business_date,
    audit.tenant_id,
    audit.action,
    audit.resource_type,
    count(*) as event_count,
    count(distinct audit.user_id) as distinct_users,
    min(audit.event_ts_utc) as first_event_utc,
    max(audit.event_ts_utc) as last_event_utc,
    current_timestamp()::timestamp_ntz as loaded_at
from {{ ref('rollup_audit') }} as audit
where {{ for_business_date('audit.business_date') }}
group by audit.tenant_id, audit.action, audit.resource_type
