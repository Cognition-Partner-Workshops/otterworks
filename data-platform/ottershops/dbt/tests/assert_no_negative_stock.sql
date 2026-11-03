select inventory_day_id from {{ ref('inventory_daily') }} where closing_stock < 0
