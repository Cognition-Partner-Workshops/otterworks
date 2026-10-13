{{ config(
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="business_date"
) }}

with resources as (
    select
        tenant_id,
        'document' as resource_type,
        document_id as resource_id,
        is_deleted as purge_flag,
        archived,
        updated_at_utc
    from {{ ref("dim_document") }}
    union all
    select
        tenant_id,
        'file' as resource_type,
        file_id as resource_id,
        is_trashed as purge_flag,
        archived,
        updated_at_utc
    from {{ ref("dim_file") }}
),
eligible_resources as (
    select
        tenant_id,
        resource_type,
        resource_id,
        case when purge_flag = 1 then 'purge' else 'cold_storage' end as retention_action,
        datediff(day, to_date(updated_at_utc), {{ business_date() }}) as days_since_update
    from resources
    where (purge_flag = 1
           and datediff(day, to_date(updated_at_utc), {{ business_date() }}) > 30)
       or (purge_flag = 0
           and archived = 1
           and datediff(day, to_date(updated_at_utc), {{ business_date() }}) > 365)
)

select
    {{ business_date() }} as business_date,
    tenant_id,
    resource_type,
    resource_id,
    retention_action,
    days_since_update,
    current_timestamp() as loaded_at
from eligible_resources
