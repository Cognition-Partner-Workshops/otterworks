select
    cast(alert_id as bigint) as alert_id,
    cast(actor_user_id as bigint) as actor_user_id,
    cast(document_id as bigint) as document_id,
    {{ audit_timestamp('alert_ts') }} as alert_ts,
    {{ legacy_text('severity_cd', 12, true) }} as severity_cd,
    {{ legacy_text('status_cd', 12, true) }} as status_cd
from {{ source('bronze_audit', 'security_alert') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
