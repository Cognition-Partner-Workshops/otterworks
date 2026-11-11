select
    ACTIVITY_DATE,
    count(distinct USER_ID) as ACTIVE_USERS,
    sum(LOGIN_COUNT) as LOGINS,
    sum(ACTION_COUNT) as ACTIONS
from {{ source('spark_users', 'USER_ACTIVITY_DAILY') }}
group by ACTIVITY_DATE
