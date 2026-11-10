{% macro pc_content_role_grant(source_relation, rejects=false, raw_input=false) %}
with input_rows as (
    select GRANT_ID as RAW_GRANT_ID, USER_ID as RAW_USER_ID, ROLE_CD,
           GRANTED_DT as RAW_GRANTED_DT from {{ source_relation }}
), converted as (
    select
{% if raw_input %}
           try_to_decimal(regexp_substr(left(RAW_GRANT_ID,20), '^[[:space:]]*[-+]?[0-9]+'),38,0) as GRANT_ID,
           try_to_decimal(regexp_substr(left(RAW_USER_ID,20), '^[[:space:]]*[-+]?[0-9]+'),38,0) as USER_ID,
           try_to_date(left(RAW_GRANTED_DT,10),'YYYY-MM-DD') as GRANTED_DT,
           (RAW_GRANT_ID is null or regexp_substr(left(RAW_GRANT_ID,20), '^[[:space:]]*[-+]?[0-9]+') is not null)
           and (RAW_USER_ID is null or regexp_substr(left(RAW_USER_ID,20), '^[[:space:]]*[-+]?[0-9]+') is not null)
           and (RAW_GRANTED_DT is null or (
               regexp_like(left(RAW_GRANTED_DT,10),'[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}')
               and try_to_date(left(RAW_GRANTED_DT,10),'YYYY-MM-DD') is not null)) as EXPRESSION_OK,
{% else %}
           RAW_GRANT_ID::number(38,0) as GRANT_ID, RAW_USER_ID::number(38,0) as USER_ID,
           RAW_GRANTED_DT::date as GRANTED_DT, true as EXPRESSION_OK,
{% endif %}
           left(upper(trim(left(ROLE_CD,12),' ')),12) as ROLE_CD
    from input_rows
), converted_rows as (
    select *,
           GRANT_ID is null or GRANT_ID not between -9223372036854775808 and 9223372036854775807
           or (USER_ID is not null and USER_ID not between -9223372036854775808 and 9223372036854775807) as WRITER_REJECT
    from converted where EXPRESSION_OK
)
{% if rejects %}
select 0::number(38,0) as ROW_TYPE, GRANT_ID, USER_ID,
       ROLE_CD::varchar(12) as ROLE_CD, GRANTED_DT::date as GRANTED_DT
from converted_rows where WRITER_REJECT
{% else %}
, candidates as (
    select *, count(*) over (partition by GRANT_ID) as KEY_COUNT
    from converted_rows where not WRITER_REJECT
), guarded as (
    select *, max(KEY_COUNT) over () as MAX_KEY_COUNT from candidates
)
select GRANT_ID, USER_ID, rpad(ROLE_CD,12,' ')::varchar(12) as ROLE_CD,
       GRANTED_DT::date as GRANTED_DT
from guarded
where 1 / iff(MAX_KEY_COUNT>1,0,1) = 1
{% endif %}
{% endmacro %}
