select
    {{ business_date() }} as business_date,
    tenant_id,
    workspace_id,
    iff(archived = 1, 'archived', 'active') as status_label,
    count(*) as document_count,
    sum(word_count::bigint) as word_count
from {{ ref('dim_document') }}
where is_deleted = 0
  and created_at_utc < dateadd(day, 1, {{ business_date() }})
group by tenant_id, workspace_id, status_label
