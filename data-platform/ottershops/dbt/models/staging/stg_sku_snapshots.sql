select sku, product_id, color, color_family, size, stock, snapshot_at, to_date(snapshot_at) as snapshot_date
from {{ source('raw', 'sku_snapshots') }}
