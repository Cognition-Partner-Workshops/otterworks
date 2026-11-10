-- T-SQL divides bigint by int as integer division, so whole GB only.
with rated as (
    select
        storage.business_date,
        storage.tenant_id,
        iff(storage.bytes_used > storage.included_bytes,
            trunc((storage.bytes_used - storage.included_bytes) / 1073741824), 0)::integer as overage_gb,
        plans.overage_cents_per_gb
    from {{ ref('rollup_storage_daily') }} as storage
    join {{ ref('dim_plan') }} as plans
        on plans.plan_id = storage.plan_id
)

select
    business_date,
    tenant_id,
    overage_gb,
    overage_gb * overage_cents_per_gb as overage_cents
from rated
