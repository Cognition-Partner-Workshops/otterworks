select s.subscription_id, s.customer_id, p.plan_code, p.monthly_fee
from {{ ref('subscription') }} s join {{ ref('plan_catalog') }} p
  on lower(rtrim(s.plan_code)) = lower(rtrim(p.plan_code))
