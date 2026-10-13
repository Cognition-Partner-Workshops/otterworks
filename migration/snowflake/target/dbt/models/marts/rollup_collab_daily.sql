-- dbo.usp_rollup_collab_daily: comments, live sessions and collaborators per document per UTC day.
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='business_date') }}

select
    {{ business_date() }} as business_date,
    events.tenant_id,
    events.document_id,
    sum(iff(events.event_type = 'comment', 1, 0)) as comment_count,
    sum(iff(events.event_type = 'session_join', 1, 0)) as session_count,
    count(distinct events.user_id) as collaborator_count,
    current_timestamp()::timestamp_ntz as loaded_at
from {{ ref('stg_collab_events') }} as events
where events.created_at >= {{ business_date() }}
  and events.created_at < dateadd(day, 1, {{ business_date() }})
  and events.tenant_id is not null
group by events.tenant_id, events.document_id
