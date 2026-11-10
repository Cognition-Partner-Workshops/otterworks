{{ config(alias='USERS_LOGIN_USERAGENT_PARSE', tags=['sfx-d1110', 'users_login_useragent_parse']) }}

-- Python 3.10 str.isspace() includes Unicode whitespace and U+001C through U+001F.
with whitespace as (
    select concat(chr(9), chr(10), chr(11), chr(12), chr(13), chr(28), chr(29),
                  chr(30), chr(31), chr(32), chr(133), chr(160), chr(5760),
                  chr(8192), chr(8193), chr(8194), chr(8195), chr(8196), chr(8197),
                  chr(8198), chr(8199), chr(8200), chr(8201), chr(8202), chr(8232),
                  chr(8233), chr(8239), chr(8287), chr(12288)) as chars
)
select LOGIN_EVENT_ID, USER_ID, EVENT_AT, IP_ADDRESS, USER_AGENT, RAW_LINE,
       coalesce(regexp_substr(coalesce(USER_AGENT, ''),
                             '(Chrome|Firefox|Safari)/[^' || whitespace.chars || ']+'), 'Other') as BROWSER
from {{ source('spark_users', 'LOGIN_EVENT') }}
cross join whitespace
