{% macro pc_audit_security_alert(source_relation, rejects=false) %}
with normalized as (
    select ALERT_ID::number(38,0) as ALERT_ID,
           ACTOR_USER_ID::number(38,0) as ACTOR_USER_ID,
           DOCUMENT_ID::number(38,0) as DOCUMENT_ID,
           ALERT_TS::timestamp_ntz(9) as ALERT_TS,
           left(upper(trim(left(SEVERITY_CD,12),' ')),12) as SEVERITY_CD,
           left(upper(trim(left(STATUS_CD,12),' ')),12) as STATUS_CD
    from {{ source_relation }}
), routed as (
    select *, case when SEVERITY_CD in ('CRITICAL','HIGH') then 1
                   when SEVERITY_CD in ('MEDIUM','LOW') then 2 else 3 end as ROUTE
    from normalized
), expressed as (
    select ALERT_ID, ACTOR_USER_ID, DOCUMENT_ID, ALERT_TS, SEVERITY_CD,
           case when ROUTE=1 and STATUS_CD='OPEN' then 'ESCALATED' else STATUS_CD end as STATUS_CD,
           ROUTE
    from routed
)
{% if rejects %}
select case when ROUTE=3 then 3 else 0 end::number(38,0) as ROW_TYPE,
       ALERT_ID, ACTOR_USER_ID, DOCUMENT_ID, ALERT_TS,
       SEVERITY_CD::varchar(12) as SEVERITY_CD, STATUS_CD::varchar(12) as STATUS_CD
from expressed where ROUTE=3 or ALERT_ID is null
{% else %}
, candidates as (
    select *, count(*) over (partition by ROUTE,ALERT_ID) as ROUTE_COUNT
    from expressed where ROUTE<>3 and ALERT_ID is not null
), guarded as (
    select *, max(ROUTE_COUNT) over () as MAX_ROUTE_COUNT from candidates
)
select ALERT_ID, ACTOR_USER_ID, DOCUMENT_ID, ALERT_TS,
       rpad(SEVERITY_CD,12,' ')::varchar(12) as SEVERITY_CD,
       rpad(STATUS_CD,12,' ')::varchar(12) as STATUS_CD
from guarded
where 1 / iff(MAX_ROUTE_COUNT>1,0,1) = 1
qualify row_number() over (partition by ALERT_ID order by ROUTE desc)=1
{% endif %}
{% endmacro %}
