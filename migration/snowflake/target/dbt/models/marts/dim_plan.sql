with source_data as (
    select plan_code, plan_name, tier, monthly_price_cents, included_seats, included_storage_gb
    from {{ source('raw', 'STG_BILLING_PLANS') }}
)

select plan_code, plan_name, tier, monthly_price_cents, included_seats, included_storage_gb
from source_data
