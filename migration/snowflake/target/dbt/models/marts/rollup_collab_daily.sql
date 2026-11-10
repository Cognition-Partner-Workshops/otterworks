select
    {{ business_date() }} as business_date,
    "tenant_id" as tenant_id,
    "document_id" as document_id,
    count_if("event_type" = 'comment') as comment_count,
    count_if("event_type" = 'session_join') as session_count,
    count(distinct "user_id") as collaborator_count
from {{ source('raw', 'STG_COLLAB_EVENTS') }}
where "created_at" >= {{ business_date() }}
  and "created_at" < dateadd(day, 1, {{ business_date() }})
  and "tenant_id" is not null
group by "tenant_id", "document_id"
