select
    cast(flag_id as bigint) as flag_id,
    cast(customer_id as bigint) as customer_id,
    cast(document_id as bigint) as document_id,
    {{ legacy_text('flag_type', 12, true) }} as flag_type,
    cast(flag_dt as date) as flag_dt,
    {{ legacy_text('status_cd', 12, true) }} as status_cd
from {{ source('bronze_audit', 'compliance_flag') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
