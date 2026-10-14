-- dbo.usp_build_mart_retention: retention actions counted per tenant, resource type and action.
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='business_date') }}

select
    {{ business_date() }} as business_date,
    retention.tenant_id,
    retention.resource_type,
    retention.retention_action,
    count(*) as item_count,
    current_timestamp()::timestamp_ntz as loaded_at
from {{ ref('rollup_retention') }} as retention
where {{ for_business_date('retention.business_date') }}
group by retention.tenant_id, retention.resource_type, retention.retention_action
