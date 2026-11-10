{% set reject_predicate = "EVENT_ID IS NULL" %}
{{ config(materialized='incremental', incremental_strategy='merge', unique_key='EVENT_ID', full_refresh=false) }}

select
    EVENT_ID::number(38,0) as EVENT_ID,
    ACTOR_USER_ID::number(38,0) as ACTOR_USER_ID,
    case when DOCUMENT_ID > 0 then DOCUMENT_ID else 0 end::number(38,0) as DOCUMENT_ID,
    case when CUSTOMER_ID > 0 then CUSTOMER_ID else 0 end::number(38,0) as CUSTOMER_ID,
    EVENT_TS::timestamp_ntz(0) as EVENT_TS,
    rpad(left(upper(trim(EVENT_TYPE,' ')),12),12,' ')::varchar(12) as EVENT_TYPE,
    left(case when DETAILS is null or trim(DETAILS,' ') = ''
        then coalesce(upper(trim(EVENT_TYPE,' ')),'') || ' by user ' || coalesce(to_varchar(ACTOR_USER_ID),'')
        else trim(DETAILS,' ') end,160)::varchar(160) as DETAILS
from {{ ref('pc_audit__stg_audit_event') }}
where not ({{ reject_predicate }})
