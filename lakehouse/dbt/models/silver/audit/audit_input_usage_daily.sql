{{ config(materialized='ephemeral') }}
select
    cast(usage_id as bigint) as usage_id,
    cast(customer_id as bigint) as customer_id,
    cast(subscription_id as bigint) as subscription_id,
    cast(usage_dt as date) as usage_dt,
    cast(units as bigint) as units,
    {{ legacy_text('usage_type', 12, true) }} as usage_type
from {{ source('bronze_billing', 'usage_daily') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
