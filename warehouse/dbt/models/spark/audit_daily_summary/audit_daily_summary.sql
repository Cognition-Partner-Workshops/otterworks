{{ config(materialized='table') }}

select
    to_date(EVENT_AT) as EVENT_DATE,
    EVENT_TYPE,
    count(*) as EVENT_COUNT,
    count(distinct ACTOR_USER_ID) as ACTORS
from {{ source('spark_audit', 'AUDIT_EVENT') }}
group by to_date(EVENT_AT), EVENT_TYPE
