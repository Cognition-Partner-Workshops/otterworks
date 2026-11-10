with previous_events as (
    select
        USER_ID,
        DOCUMENT_ID,
        EVENT_AT,
        lag(EVENT_AT) over (
            partition by USER_ID, DOCUMENT_ID order by EVENT_AT
        ) as PREVIOUS_EVENT_AT
    from {{ source('spark_documents', 'COLLAB_SESSION') }}
), session_boundaries as (
    select
        USER_ID,
        DOCUMENT_ID,
        EVENT_AT,
        case
            when PREVIOUS_EVENT_AT is null
                or timestampdiff(microsecond, PREVIOUS_EVENT_AT, EVENT_AT) > 1800000000
            then 1 else 0
        end as NEW_SESSION
    from previous_events
), numbered_events as (
    select
        USER_ID,
        DOCUMENT_ID,
        EVENT_AT,
        sum(NEW_SESSION) over (
            partition by USER_ID, DOCUMENT_ID order by EVENT_AT
            range between unbounded preceding and current row
        ) as SESSION_NUMBER
    from session_boundaries
)
select
    USER_ID,
    DOCUMENT_ID,
    SESSION_NUMBER,
    min(EVENT_AT) as START_AT,
    max(EVENT_AT) as END_AT
from numbered_events
group by USER_ID, DOCUMENT_ID, SESSION_NUMBER
