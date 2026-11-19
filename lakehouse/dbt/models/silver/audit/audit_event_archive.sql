select
    cast(row_number() over (order by event_id) as bigint) as archive_id,
    actor_user_id, document_id, event_ts, event_type, details
from {{ ref('audit_event') }}
where {{ 'true' if var('audit_archive_enabled', false) else 'false' }}
    and event_ts < date_sub(to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd'), 2555)
