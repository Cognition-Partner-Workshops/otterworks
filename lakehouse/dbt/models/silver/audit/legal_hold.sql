select
    cast(hold_id as bigint) as hold_id,
    cast(document_id as bigint) as document_id,
    cast(customer_id as bigint) as customer_id,
    cast(start_dt as date) as start_dt,
    {{ legacy_text('reason_text', 120) }} as reason_text,
    {{ legacy_text('status_cd', 12, true) }} as status_cd
from {{ source('bronze_audit', 'legal_hold') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
