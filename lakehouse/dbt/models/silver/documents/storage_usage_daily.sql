select distinct 
    cast(storage_usage_id as bigint) as storage_usage_id,
    cast(customer_id as bigint) as customer_id,
    cast(owner_user_id as bigint) as owner_user_id,
    cast(usage_dt as date) as usage_dt,
    cast(bytes_used as bigint) as bytes_used,
    cast(object_count as int) as object_count
from {{ ref('stg_storage_usage_daily') }}
