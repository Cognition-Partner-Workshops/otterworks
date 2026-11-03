-- A line can't be returned more times, or refunded for more, than it was bought for.
select r.order_line_id
from {{ ref('fct_returns') }} r
join {{ ref('fct_order_lines') }} l on l.order_line_id = r.order_line_id
join {{ ref('fct_orders') }} o on o.order_id = l.order_id
group by r.order_line_id, l.quantity, l.line_total, o.tax_cents, o.subtotal_cents, o.discount_cents
having sum(r.quantity) > l.quantity
    or sum(r.refund_amount) > l.line_total + o.tax_cents / 100 + 0.01
