select order_number from {{ ref('fct_orders') }}
where total_cents != subtotal_cents - discount_cents + shipping_cents + fees_cents + tax_cents
