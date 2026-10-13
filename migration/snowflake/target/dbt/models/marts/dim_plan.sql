select
    "id" as plan_id,
    "code" as plan_code,
    "tier" as plan_tier,
    trunc("monthly_fee" * 100)::integer as monthly_fee_cents,
    "included_units" as included_units,
    "included_bytes" as included_bytes,
    "overage_cents_per_gb" as overage_cents_per_gb,
    case "tier"
        when 'starter' then 25
        when 'growth' then 75
        when 'scale' then 250
        else 0
    end as seat_limit,
    iff(lower("active"::varchar) in ('1', 'true', 't', 'yes', 'y'), 1, 0) as is_active
from {{ source('raw', 'STG_BILLING_PLANS') }}
