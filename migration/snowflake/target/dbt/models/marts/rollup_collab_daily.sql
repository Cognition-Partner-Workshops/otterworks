{{ config(
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="business_date"
) }}

select
    {{ business_date() }} as business_date,
    c."tenant_id" as tenant_id,
    c."document_id" as document_id,
    sum(case when c."event_type" = 'comment' then 1 else 0 end) as comment_count,
    sum(case when c."event_type" = 'session_join' then 1 else 0 end) as session_count,
    count(distinct c."user_id") as collaborator_count,
    current_timestamp() as loaded_at
from {{ source("raw", "STG_COLLAB_EVENTS") }} as c
where c."created_at" >= {{ business_date() }}
  and c."created_at" < dateadd(day, 1, {{ business_date() }})
  and c."tenant_id" is not null
group by
    c."tenant_id",
    c."document_id"
