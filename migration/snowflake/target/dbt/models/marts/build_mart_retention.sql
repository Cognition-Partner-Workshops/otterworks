{{ config(
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="business_date"
) }}

select
    business_date,
    tenant_id,
    resource_type,
    retention_action,
    count(*) as item_count
from {{ ref("rollup_retention") }}
where business_date = {{ business_date() }}
group by business_date, tenant_id, resource_type, retention_action
