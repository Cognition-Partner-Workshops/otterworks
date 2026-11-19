{{ config(materialized='ephemeral') }}
select
    cast(plan_id as bigint) as plan_id,
    {{ legacy_text('plan_code', 10, true) }} as plan_code,
    {{ legacy_text('plan_name', 80) }} as plan_name,
    cast(monthly_fee as decimal(18,2)) as monthly_fee,
    {{ legacy_text('currency_cd', 3, true) }} as currency_cd
from {{ source('bronze_billing', 'plan_catalog') }}
where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')
