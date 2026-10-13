{{ config(
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="business_date"
) }}

select
    business_date,
    tenant_id,
    action,
    resource_type,
    count(*) as event_count,
    count(distinct user_id) as distinct_users,
    min(event_ts_utc) as first_event_utc,
    max(event_ts_utc) as last_event_utc
from {{ ref("rollup_audit") }}
where business_date = {{ business_date() }}
group by business_date, tenant_id, action, resource_type
