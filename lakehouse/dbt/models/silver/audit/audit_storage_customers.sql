{{ config(materialized='ephemeral') }}
select u.customer_id, s.subscription_id, sum(u.bytes_used) as units
from {{ ref('audit_input_storage_usage_daily') }} u
join (select customer_id, min(subscription_id) as subscription_id from {{ ref('audit_input_subscription') }} group by customer_id) s
on u.customer_id=s.customer_id
where u.usage_dt >= trunc(to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd'), 'MM') and u.usage_dt < add_months(trunc(to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd'), 'MM'), 1)
group by u.customer_id, s.subscription_id
