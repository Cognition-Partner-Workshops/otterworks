select
    cast(policy_id as bigint) as policy_id,
    {{ legacy_text('policy_name', 80) }} as policy_name,
    cast(retention_days as int) as retention_days,
    cast(effective_dt as date) as effective_dt,
    {{ legacy_text('status_cd', 12, true) }} as status_cd
from {{ source('bronze_audit', 'retention_policy') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
