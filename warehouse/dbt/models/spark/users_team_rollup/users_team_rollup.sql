select
    t.TEAM_ID,
    t.TEAM_NAME,
    count(m.USER_ID) as MEMBERS
from {{ source('spark_users', 'TEAM') }} t
left join {{ source('spark_users', 'TEAM_MEMBER') }} m on t.TEAM_ID = m.TEAM_ID
left join {{ source('spark_users', 'APP_USER') }} u on m.USER_ID = u.USER_ID
group by t.TEAM_ID, t.TEAM_NAME
