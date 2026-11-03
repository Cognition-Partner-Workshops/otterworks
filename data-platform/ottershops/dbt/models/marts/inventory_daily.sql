with eod as (
  select * exclude (_rn) from (
    select *, row_number() over (partition by sku, snapshot_date order by snapshot_at desc) as _rn
    from {{ ref('stg_sku_snapshots') }}
  ) where _rn = 1
),
sold as (
  select sku, order_date, sum(quantity) as units_sold
  from {{ ref('fct_order_lines') }} group by 1, 2
)
select
  e.snapshot_date || '-' || e.sku as inventory_day_id,
  e.snapshot_date, e.sku, e.product_id, e.color, e.size, e.stock as closing_stock,
  coalesce(s.units_sold, 0) as units_sold,
  e.stock = 0 as is_sold_out, e.stock between 1 and 5 as is_low_stock
from eod e
left join sold s on s.sku = e.sku and s.order_date = e.snapshot_date
