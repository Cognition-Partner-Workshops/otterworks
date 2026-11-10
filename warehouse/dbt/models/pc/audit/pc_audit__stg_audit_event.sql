{% set reject_predicate = "(EVENT_ID IS NOT NULL AND TRY_TO_NUMBER(TO_VARCHAR(EVENT_ID),38,0) IS NULL) OR (ACTOR_USER_ID IS NOT NULL AND TRY_TO_NUMBER(TO_VARCHAR(ACTOR_USER_ID),38,0) IS NULL) OR (DOCUMENT_ID IS NOT NULL AND TRY_TO_NUMBER(TO_VARCHAR(DOCUMENT_ID),38,0) IS NULL) OR (CUSTOMER_ID IS NOT NULL AND TRY_TO_NUMBER(TO_VARCHAR(CUSTOMER_ID),38,0) IS NULL) OR (EVENT_TS IS NOT NULL AND TRY_TO_TIMESTAMP_NTZ(TO_VARCHAR(EVENT_TS,'YYYY-MM-DD HH24:MI:SS'),'YYYY-MM-DD HH24:MI:SS') IS NULL)" %}
{{ config(materialized='table') }}

select
    try_to_number(to_varchar(EVENT_ID),38,0)::number(38,0) as EVENT_ID,
    try_to_number(to_varchar(ACTOR_USER_ID),38,0)::number(38,0) as ACTOR_USER_ID,
    try_to_number(to_varchar(DOCUMENT_ID),38,0)::number(38,0) as DOCUMENT_ID,
    try_to_number(to_varchar(CUSTOMER_ID),38,0)::number(38,0) as CUSTOMER_ID,
    try_to_timestamp_ntz(to_varchar(EVENT_TS,'YYYY-MM-DD HH24:MI:SS'),
                         'YYYY-MM-DD HH24:MI:SS')::timestamp_ntz(0) as EVENT_TS,
    trim(left(EVENT_TYPE,12),' ')::varchar(200) as EVENT_TYPE,
    trim(left(DETAILS,160),' ')::varchar(200) as DETAILS
from {{ source('unt3_pc_src','AUDIT_EVENT') }}
where not ({{ reject_predicate }})
