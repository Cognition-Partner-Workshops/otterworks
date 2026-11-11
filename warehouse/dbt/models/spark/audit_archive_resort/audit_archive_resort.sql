{{ config(materialized='table', cluster_by=['EVENT_TYPE', 'EVENT_AT', 'AUDIT_EVENT_ARCHIVE_ID']) }}

select
    AUDIT_EVENT_ARCHIVE_ID,
    ACTOR_USER_ID,
    DOCUMENT_ID,
    EVENT_TYPE,
    EVENT_AT,
    DETAILS
from {{ source('spark_audit', 'AUDIT_EVENT_ARCHIVE') }}
order by EVENT_TYPE, EVENT_AT, AUDIT_EVENT_ARCHIVE_ID
