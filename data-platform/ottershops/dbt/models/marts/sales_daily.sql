select
  l.order_date || '-' || coalesce(l.department, 'unknown') as sales_day_id,
  l.order_date, coalesce(l.department, 'unknown') as department,
  count(distinct l.order_id) as orders, sum(l.quantity) as units,
  sum(l.unit_list_price * l.quantity) as gross_list_sales,
  sum(l.line_total) as net_merchandise_sales,
  sum(l.total_savings) as total_savings,
  count(distinct iff(l.fulfillment = 'PICKUP', l.order_id, null)) as pickup_orders
from {{ ref('fct_order_lines') }} l
group by 1, 2, 3
