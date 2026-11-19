select
    cast(user_id as bigint) as user_id,
    {{ legacy_text('display_name', 60, false) }} as display_name,
    {{ legacy_text('email', 120, false) }} as email,
    {{ legacy_text('status_cd', 12, true) }} as status_cd,
    cast(created_dt as date) as created_dt
from {{ users_snapshot('app_user') }}
