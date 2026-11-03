with latest as (
  select * from {{ ref('stg_sku_snapshots') }}
  where snapshot_at = (select max(snapshot_at) from {{ ref('stg_sku_snapshots') }})
),
stock as (
  select product_id, count(*) as sku_count, sum(stock) as units_in_stock,
    count_if(stock = 0) as sold_out_skus, count_if(stock between 1 and 5) as low_stock_skus
  from latest group by 1
),
cols as (
  select product_id, array_agg(collection_slug) within group (order by collection_slug) as collections
  from {{ ref('stg_product_collections') }} group by 1
)
select
  p.id as product_id, p.name, p.label, p.department, p.category, p.fit,
  p.list_price_cents / 100 as list_price, p.markdown_price_cents / 100 as markdown_price,
  p.markdown_price_cents is not null as is_markdown, p.rating, p.review_count, p.is_new,
  c.collections, s.sku_count, s.units_in_stock, s.sold_out_skus, s.low_stock_skus,
  coalesce(s.units_in_stock, 0) = 0 as is_sold_out, p.created_at
from {{ ref('stg_products') }} p
left join stock s on s.product_id = p.id
left join cols c on c.product_id = p.id
