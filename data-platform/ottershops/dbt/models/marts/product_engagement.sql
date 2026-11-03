-- Per-product demand signals beyond sales: written reviews and fit, favorites, back-in-stock asks, returns.
with reviews as (
  select product_id, count(*) as written_reviews, avg(rating) as avg_written_rating,
    count_if(fit_note = 'Runs small') as fit_runs_small, count_if(fit_note = 'True to size') as fit_true_to_size,
    count_if(fit_note = 'Runs large') as fit_runs_large, sum(helpful_count) as helpful_votes
  from {{ ref('stg_reviews') }} group by 1
),
favorites as (
  select product_id, count(*) as favorites, count_if(customer_id is not null) as member_favorites
  from {{ ref('stg_wishlist_items') }} group by 1
),
skus as (
  select sku, product_id from {{ ref('stg_sku_snapshots') }} qualify row_number() over (partition by sku order by snapshot_at desc) = 1
),
alerts as (
  select s.product_id, count_if(n.status = 'PENDING') as pending_stock_alerts
  from {{ ref('stg_stock_notifications') }} n join skus s on s.sku = n.sku group by 1
),
sold as (
  select product_id, sum(quantity) as units_sold from {{ ref('fct_order_lines') }} group by 1
),
returned as (
  select product_id, sum(quantity) as units_returned, sum(refund_amount) as refunded,
    mode(reason) as top_return_reason
  from {{ ref('fct_returns') }} group by 1
)
select
  p.product_id, p.name, p.department, p.category, p.is_sold_out,
  coalesce(r.written_reviews, 0) as written_reviews, r.avg_written_rating,
  coalesce(r.fit_runs_small, 0) as fit_runs_small, coalesce(r.fit_true_to_size, 0) as fit_true_to_size,
  coalesce(r.fit_runs_large, 0) as fit_runs_large, coalesce(r.helpful_votes, 0) as helpful_votes,
  coalesce(f.favorites, 0) as favorites, coalesce(f.member_favorites, 0) as member_favorites,
  coalesce(a.pending_stock_alerts, 0) as pending_stock_alerts,
  coalesce(s.units_sold, 0) as units_sold, coalesce(x.units_returned, 0) as units_returned,
  coalesce(x.refunded, 0) as refunded, x.top_return_reason,
  iff(coalesce(s.units_sold, 0) = 0, null, coalesce(x.units_returned, 0) / s.units_sold) as return_rate
from {{ ref('dim_products') }} p
left join reviews r on r.product_id = p.product_id
left join favorites f on f.product_id = p.product_id
left join alerts a on a.product_id = p.product_id
left join sold s on s.product_id = p.product_id
left join returned x on x.product_id = p.product_id
