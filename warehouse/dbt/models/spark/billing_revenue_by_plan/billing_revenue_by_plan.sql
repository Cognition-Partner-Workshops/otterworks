-- Replaces lake billing/billing_revenue_by_plan.
select
    p.PLAN_ID,
    p.PLAN_NAME,
    sum(l.AMOUNT) as REVENUE
from {{ source('spark_billing', 'INVOICE_LINE') }} l
join {{ source('spark_billing', 'PLAN_CATALOG') }} p
    on l.PLAN_ID = p.PLAN_ID
group by p.PLAN_ID, p.PLAN_NAME
