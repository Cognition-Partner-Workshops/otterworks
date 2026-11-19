select
    cast(grant_id as bigint) as grant_id,
    cast(user_id as bigint) as user_id,
    {{ legacy_text('role_cd', 12, true) }} as role_cd,
    cast(granted_dt as date) as granted_dt
from {{ users_snapshot('role_grant') }}
