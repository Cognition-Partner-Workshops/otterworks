select
    cast(event_id as bigint) as event_id,
    cast(actor_user_id as bigint) as actor_user_id,
    cast(document_id as bigint) as document_id,
    cast(customer_id as bigint) as customer_id,
    {{ audit_timestamp('event_ts') }} as event_ts,
    {{ legacy_text('event_type', 200) }} as event_type,
    {{ legacy_text('details', 200) }} as details
from {{ source('bronze_audit', 'audit_event') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
