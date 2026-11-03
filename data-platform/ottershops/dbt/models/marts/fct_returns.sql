-- One row per returned order line.
select
  r.id || '-' || rl.line_no as return_line_id,
  r.id as return_id, r.return_number, r.order_id, o.order_number,
  r.order_id || '-' || rl.line_no as order_line_id,
  l.product_id, l.department, l.category, l.name, l.size,
  rl.quantity, rl.reason, r.method, r.status,
  rl.refund_cents / 100 as refund_amount,
  r.created_at as requested_at, to_date(r.created_at) as requested_date,
  datediff('day', o.created_at, r.created_at) as days_after_order
from {{ ref('stg_return_lines') }} rl
join {{ ref('stg_returns') }} r on r.id = rl.return_id
join {{ ref('stg_orders') }} o on o.id = r.order_id
left join {{ ref('fct_order_lines') }} l on l.order_line_id = r.order_id || '-' || rl.line_no
