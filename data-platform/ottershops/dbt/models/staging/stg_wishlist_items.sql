-- Favorites are re-snapshotted whole on change, so the current state is the latest load.
select * exclude (_loaded_at) from {{ source('raw', 'wishlist_items') }}
where _loaded_at = (select max(_loaded_at) from {{ source('raw', 'wishlist_items') }})
