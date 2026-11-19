select 
    cast(folder_id as bigint) as folder_id,
    cast(owner_user_id as bigint) as owner_user_id,
    cast(customer_id as bigint) as customer_id,
    {{ legacy_text('folder_name', 100) }} as folder_name,
    cast(created_dt as date) as created_dt
from {{ ref('stg_folder') }}
