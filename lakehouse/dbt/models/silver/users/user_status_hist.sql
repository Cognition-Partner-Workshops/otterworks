select
    cast(status_history_id as bigint) as status_history_id,
    cast(user_id as bigint) as user_id,
    {{ legacy_text('status_cd', 12, true) }} as status_cd,
    cast(valid_from as date) as valid_from,
    cast(valid_to as date) as valid_to
from {{ users_snapshot('user_status_hist') }}
