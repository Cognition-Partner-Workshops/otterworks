{{ config(
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="business_date"
) }}

with live_documents as (
    select
        tenant_id,
        workspace_id,
        word_count,
        case when archived = 1 then 'archived' else 'active' end as status_label
    from {{ ref("dim_document") }}
    where is_deleted = 0
      and created_at_utc < dateadd(day, 1, {{ business_date() }})
)

select
    {{ business_date() }} as business_date,
    tenant_id,
    workspace_id,
    status_label,
    count(*) as document_count,
    sum(cast(word_count as bigint)) as word_count,
    current_timestamp() as loaded_at
from live_documents
group by
    tenant_id,
    workspace_id,
    status_label
