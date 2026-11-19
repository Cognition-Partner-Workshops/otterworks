select
    cast(recon_id as bigint) as recon_id,
    cast(business_dt as date) as business_dt,
    cast(customer_id as bigint) as customer_id,
    cast(source_count as bigint) as source_count,
    cast(target_count as bigint) as target_count,
    cast(difference_count as bigint) as difference_count
from {{ source('bronze_audit', 'audit_recon') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
