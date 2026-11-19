{{ config(materialized='ephemeral') }}
select
    cast(subscription_id as bigint) as subscription_id,
    cast(customer_id as bigint) as customer_id,
    {{ legacy_text('plan_code', 10) }} as plan_code,
    cast(start_dt as date) as start_dt,
    cast(end_dt as date) as end_dt,
    {{ legacy_text('status_cd', 12, true) }} as status_cd
from {{ source('bronze_billing', 'subscription') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
