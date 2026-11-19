select
    cast(export_id as bigint) as export_id,
    cast(user_id as bigint) as user_id,
    cast(customer_id as bigint) as customer_id,
    cast(request_dt as date) as request_dt,
    {{ legacy_text('status_cd', 12, true) }} as status_cd,
    cast(row_count as bigint) as row_count
from {{ source('bronze_audit', 'data_export_req') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
