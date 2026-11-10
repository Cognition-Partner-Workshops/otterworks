with activity as (
    select
        iff(LOGIN_COUNT > 12, 0, USER_ID) as user_key,
        ACTIVITY_DATE as activity_date,
        sum(ACTION_COUNT) as action_count
    from {{ source('spark_users', 'USER_ACTIVITY_DAILY') }}
    group by 1, 2
),

logins as (
    select
        iff(hour(EVENT_AT) < 8, 0, USER_ID) as user_key,
        max(USER_AGENT) as user_agent,
        coalesce(sum(octet_length(RAW_LINE)), 0) + greatest(count(RAW_LINE) - 1, 0) as login_text_bytes
    from {{ source('spark_users', 'LOGIN_EVENT') }}
    group by 1
)

select
    coalesce(a.ACTOR_USER_ID, 0) as user_key,
    a.AUDIT_EVENT_ID as audit_event_id,
    a.EVENT_AT as event_at,
    d.activity_date,
    d.action_count,
    l.user_agent,
    l.login_text_bytes
from {{ source('spark_audit', 'AUDIT_EVENT') }} as a
inner join activity as d on coalesce(a.ACTOR_USER_ID, 0) = d.user_key
inner join logins as l on coalesce(a.ACTOR_USER_ID, 0) = l.user_key
