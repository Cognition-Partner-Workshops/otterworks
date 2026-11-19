select
    cast(team_member_id as bigint) as team_member_id,
    cast(team_id as bigint) as team_id,
    cast(user_id as bigint) as user_id,
    {{ legacy_text('role_cd', 12, true) }} as role_cd,
    cast(joined_dt as date) as joined_dt
from {{ users_snapshot('team_member') }}
