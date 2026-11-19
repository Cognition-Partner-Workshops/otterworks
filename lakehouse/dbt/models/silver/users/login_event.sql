select
    cast(login_id as bigint) as login_id,
    cast(user_id as bigint) as user_id,
    cast(login_ts as timestamp) as login_ts,
    {{ legacy_text('result_cd', 12, true) }} as result_cd,
    {{ legacy_text('client_type', 12, true) }} as client_type
from {{ users_snapshot('login_event') }}
