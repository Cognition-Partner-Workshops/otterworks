select
    cast(usage_id as bigint) as usage_id,
    cast(customer_id as bigint) as customer_id,
    cast(subscription_id as bigint) as subscription_id,
    cast(usage_dt as date) as usage_dt,
    cast(units as bigint) as units,
    {{ legacy_text('usage_type', 12, true) }} as usage_type
from {{ ref('stg_usage_daily') }}
