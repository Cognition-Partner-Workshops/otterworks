select
  l.order_id || '-' || l.line_no as order_line_id,
  l.order_id, o.order_number, l.line_no, l.sku, l.product_id,
  p.department, p.category, l.name, l.color, l.size, l.quantity,
  l.unit_list_cents / 100 as unit_list_price, l.unit_price_cents / 100 as unit_price,
  l.discount_cents / 100 as code_discount, l.line_total_cents / 100 as line_total,
  (l.unit_list_cents * l.quantity - l.line_total_cents) / 100 as total_savings,
  coalesce(pc.collection_slug, 'core') as merch_program,
  o.fulfillment, o.created_at, to_date(o.created_at) as order_date
from {{ ref('stg_order_lines') }} l
join {{ ref('stg_orders') }} o on o.id = l.order_id
left join {{ ref('stg_products') }} p on p.id = l.product_id
left join {{ ref('stg_product_collections') }} pc
  on pc.product_id = l.product_id and pc.collection_slug in ('sale', 'new-arrivals', 'essentials-forever')
