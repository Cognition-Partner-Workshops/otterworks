select product_id, collection_slug
from {{ source('raw', 'product_collections') }}
where _loaded_at = (select max(_loaded_at) from {{ source('raw', 'product_collections') }})
