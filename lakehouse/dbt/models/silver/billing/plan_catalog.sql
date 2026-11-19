select
    cast(plan_id as bigint) as plan_id,
    {{ legacy_text('plan_code', 10, true) }} as plan_code,
    {{ legacy_text('plan_name', 80) }} as plan_name,
    cast(monthly_fee as decimal(14,2)) as monthly_fee,
    {{ legacy_text('currency_cd', 3, true) }} as currency_cd
from {{ ref('stg_plan_catalog') }}
