{{ config(alias='USERS_LOGIN_USERAGENT_PARSE', tags=['sfx-d1110', 'users_login_useragent_parse']) }}

select LOGIN_EVENT_ID, USER_ID, EVENT_AT, IP_ADDRESS, USER_AGENT, RAW_LINE,
       coalesce(regexp_substr(coalesce(USER_AGENT, ''), '(Chrome|Firefox|Safari)/[^[:space:]]+'), 'Other') as BROWSER
from {{ source('spark_users', 'LOGIN_EVENT') }}
