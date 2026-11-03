with o as (
  select customer_id, count(*) as order_count, sum(total_cents) / 100 as lifetime_value,
    min(created_at) as first_order_at, max(created_at) as last_order_at
  from {{ ref('stg_orders') }} where customer_id is not null group by 1
)
select
  c.id as customer_id, c.email, c.first_name, c.last_name, c.rewards_points, c.created_at,
  coalesce(o.order_count, 0) as order_count, coalesce(o.lifetime_value, 0) as lifetime_value,
  o.first_order_at, o.last_order_at
from {{ ref('stg_customers') }} c
left join o on o.customer_id = c.id
