{% macro pc_content_login_event(source_relation, rejects=false, raw_input=false) %}
with input_rows as (
    select LOGIN_ID as RAW_LOGIN_ID, USER_ID as RAW_USER_ID, LOGIN_TS as RAW_LOGIN_TS,
           RESULT_CD, CLIENT_TYPE from {{ source_relation }}
), converted as (
    select
{% if raw_input %}
           try_to_decimal(regexp_substr(left(RAW_LOGIN_ID,20), '^[[:space:]]*[-+]?[0-9]+'),38,0) as LOGIN_ID,
           try_to_decimal(regexp_substr(left(RAW_USER_ID,20), '^[[:space:]]*[-+]?[0-9]+'),38,0) as USER_ID,
           try_to_timestamp_ntz(left(RAW_LOGIN_TS,19),'YYYY-MM-DD HH24:MI:SS') as LOGIN_TS,
           (RAW_LOGIN_ID is null or regexp_substr(left(RAW_LOGIN_ID,20), '^[[:space:]]*[-+]?[0-9]+') is not null)
           and (RAW_USER_ID is null or regexp_substr(left(RAW_USER_ID,20), '^[[:space:]]*[-+]?[0-9]+') is not null)
           and (RAW_LOGIN_TS is null or try_to_timestamp_ntz(left(RAW_LOGIN_TS,19),'YYYY-MM-DD HH24:MI:SS') is not null) as EXPRESSION_OK,
{% else %}
           RAW_LOGIN_ID::number(38,0) as LOGIN_ID, RAW_USER_ID::number(38,0) as USER_ID,
           RAW_LOGIN_TS::timestamp_ntz(9) as LOGIN_TS, true as EXPRESSION_OK,
{% endif %}
           left(upper(trim(left(RESULT_CD,12),' ')),12) as RESULT_CD,
           left(upper(trim(left(CLIENT_TYPE,12),' ')),12) as CLIENT_TYPE
    from input_rows
), routed as (
    select *, case when RESULT_CD='SUCCESS' then 1
                   when RESULT_CD in ('FAILED','LOCKED','MFA_FAILED') then 2 else 3 end as ROUTE,
           LOGIN_ID is null or LOGIN_ID not between -9223372036854775808 and 9223372036854775807
           or (USER_ID is not null and USER_ID not between -9223372036854775808 and 9223372036854775807) as WRITER_REJECT
    from converted where EXPRESSION_OK
)
{% if rejects %}
select iff(LOGIN_ID is not null and LOGIN_ID between -9223372036854775808 and 9223372036854775807,1,0)::number(38,0) as ROW_TYPE,
       LOGIN_ID, USER_ID, LOGIN_TS::timestamp_ntz(9) as LOGIN_TS,
       RESULT_CD::varchar(12) as RESULT_CD, CLIENT_TYPE::varchar(12) as CLIENT_TYPE
from routed where ROUTE<>3 and WRITER_REJECT
{% else %}
, candidates as (
    select *, count(*) over (partition by ROUTE,LOGIN_ID) as ROUTE_COUNT
    from routed where ROUTE<>3 and not WRITER_REJECT
), guarded as (
    select *, max(ROUTE_COUNT) over () as MAX_ROUTE_COUNT from candidates
)
select LOGIN_ID, USER_ID, LOGIN_TS::timestamp_ntz(9) as LOGIN_TS,
       rpad(RESULT_CD,12,' ')::varchar(12) as RESULT_CD,
       rpad(CLIENT_TYPE,12,' ')::varchar(12) as CLIENT_TYPE
from guarded
where 1 / iff(MAX_ROUTE_COUNT>1,0,1) = 1
qualify row_number() over (partition by LOGIN_ID order by ROUTE desc)=1
{% endif %}
{% endmacro %}
