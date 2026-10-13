with source_data as (
    select tenant_id, tenant_name, plan_code, region_code, status, created_at
    from {{ source('raw', 'STG_BILLING_TENANTS') }}
)

select tenant_id, tenant_name, plan_code, region_code, status, created_at
from source_data
