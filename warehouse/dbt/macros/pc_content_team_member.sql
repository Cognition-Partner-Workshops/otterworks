{% macro pc_content_team_member(source_relation, rejects=false, raw_input=false) %}
with input_rows as (
    select left(TEAM_MEMBER_ID::varchar,20) as RAW_TEAM_MEMBER_ID,
           left(TEAM_ID::varchar,20) as RAW_TEAM_ID,
           left(USER_ID::varchar,20) as RAW_USER_ID,
           left(ROLE_CD,12) as RAW_ROLE_CD,
{% if raw_input %}
           left(JOINED_DT,10) as RAW_JOINED_DT
{% else %}
           to_char(JOINED_DT,'YYYY-MM-DD') as RAW_JOINED_DT
{% endif %}
    from {{ source_relation }}
), parsed as (
    select *,
{% for column in ['TEAM_MEMBER_ID','TEAM_ID','USER_ID'] %}
           {{ unt8_integer_prefix('RAW_' ~ column) }} as PREFIX_{{ column }},
{% endfor %}
           {{ unt8_decimal_digits('RAW_JOINED_DT') }} as NORMAL_DATE
    from input_rows
), dates as (
    select *, try_to_date(NORMAL_DATE,'YYYY-MM-DD') as JOINED_DT
    from parsed
), converted as (
    select *,
{% for column in ['TEAM_MEMBER_ID','TEAM_ID','USER_ID'] %}
           try_to_decimal(PREFIX_{{ column }},38,0) as {{ column }},
{% endfor %}
           {{ unt8_python_upper("trim(RAW_ROLE_CD,' ')") }} as UPPER_ROLE,
           (RAW_TEAM_MEMBER_ID is null or PREFIX_TEAM_MEMBER_ID is not null)
           and (RAW_TEAM_ID is null or PREFIX_TEAM_ID is not null)
           and (RAW_USER_ID is null or PREFIX_USER_ID is not null)
           and (RAW_JOINED_DT is null or
                (regexp_like(NORMAL_DATE,'[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}')
                 and left(NORMAL_DATE,4) <> '0000' and JOINED_DT is not null)) as EXPRESSION_OK
    from dates
), classified as (
    select *, left(UPPER_ROLE,12) as ROLE_CD,
           TEAM_MEMBER_ID is null or TEAM_MEMBER_ID not between -9223372036854775808 and 9223372036854775807
           or (TEAM_ID is not null and TEAM_ID not between -9223372036854775808 and 9223372036854775807)
           or (USER_ID is not null and USER_ID not between -9223372036854775808 and 9223372036854775807)
           or contains(left(UPPER_ROLE,12),chr(0)) as WRITER_REJECT
    from converted
)
{% if rejects %}
select case when not EXPRESSION_OK then 'transformation_drop'
            when WRITER_REJECT then 'writer_reject' else 'accepted' end as CLASSIFICATION,
       TEAM_MEMBER_ID,TEAM_ID,USER_ID,ROLE_CD,JOINED_DT,
       count(*) over (partition by CLASSIFICATION) as CLASSIFICATION_COUNT
from classified
{% else %}
, candidates as (
    select *, count(*) over (partition by TEAM_MEMBER_ID) as KEY_COUNT
    from classified where EXPRESSION_OK and not coalesce(WRITER_REJECT,false)
), guarded as (
    select *, max(KEY_COUNT) over () as MAX_KEY_COUNT from candidates
)
select TEAM_MEMBER_ID,TEAM_ID,USER_ID,
       rpad(ROLE_CD,12,' ')::varchar(12) as ROLE_CD,JOINED_DT::date as JOINED_DT
from guarded where 1 / iff(MAX_KEY_COUNT>1,0,1)=1
{% endif %}
{% endmacro %}
