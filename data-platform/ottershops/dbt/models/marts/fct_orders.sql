with lines as (
  select order_id, sum(quantity) as units, count(*) as line_count
  from {{ ref('stg_order_lines') }} group by 1
)
select
  o.id as order_id, o.order_number, o.customer_id, o.email,
  o.customer_id is not null as is_member,
  o.status, o.fulfillment, o.shipping_method, o.store_id, s.name as store_name,
  coalesce(o.ship_state, s.state) as state, o.promo_code,
  l.units, l.line_count,
  o.subtotal_cents / 100 as subtotal, o.discount_cents / 100 as discount,
  o.shipping_cents / 100 as shipping, o.fees_cents / 100 as fees,
  o.tax_cents / 100 as tax, o.total_cents / 100 as total,
  o.subtotal_cents, o.discount_cents, o.shipping_cents, o.fees_cents, o.tax_cents, o.total_cents,
  o.card_brand, o.created_at, to_date(o.created_at) as order_date
from {{ ref('stg_orders') }} o
left join lines l on l.order_id = o.id
left join {{ ref('stg_stores') }} s on s.id = o.store_id
