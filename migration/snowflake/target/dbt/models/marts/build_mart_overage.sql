select
    storage.business_date,
    storage.tenant_id,
    tenants.tenant_name,
    tenants.plan_tier,
    storage.bytes_used,
    storage.included_bytes,
    rated.overage_gb,
    plans.overage_cents_per_gb,
    rated.overage_cents
from {{ ref('rollup_storage_daily') }} as storage
join {{ ref('rate_overage') }} as rated
    on rated.business_date = storage.business_date
   and rated.tenant_id = storage.tenant_id
join {{ ref('dim_tenant') }} as tenants
    on tenants.tenant_id = storage.tenant_id
join {{ ref('dim_plan') }} as plans
    on plans.plan_id = storage.plan_id
where rated.overage_gb is not null
