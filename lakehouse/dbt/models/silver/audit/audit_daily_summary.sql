select
    cast(summary_id as bigint) as summary_id,
    cast(summary_dt as date) as summary_dt,
    cast(customer_id as bigint) as customer_id,
    cast(event_count as bigint) as event_count,
    cast(export_count as int) as export_count
from {{ source('bronze_audit', 'audit_daily_summary') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
