select
    cast(profile_id as bigint) as profile_id,
    cast(user_id as bigint) as user_id,
    {{ legacy_text('title', 60, false) }} as title,
    {{ legacy_text('country_cd', 2, true) }} as country_cd,
    {{ legacy_text('timezone', 40, false) }} as timezone
from {{ users_snapshot('user_profile') }}
