{#- Runner SQ filter EVENT_TS < CURRENT_DATE - $$ARCHIVE_DAYS (m_SFX_AUDIT_EVENT_ARCHIVE.XML:39), evaluated
    on the UTC date like the runner's PostgreSQL session. Sequence NEXTVAL follows SQ read order, which is EVENT_ID
    order for the audit target. Replay appends only tuple occurrences not yet archived. -#}
{% macro pc_audit_event_archive(source_relation) %}
{%- set archive_days = var('pc_audit_archive_days', 2555) | int -%}
{%- set sequence_start = var('pc_audit_archive_sequence_start', 1) | int -%}
with eligible as (
    select
        EVENT_ID,
        ACTOR_USER_ID::number(38,0) as ACTOR_USER_ID,
        DOCUMENT_ID::number(38,0) as DOCUMENT_ID,
        EVENT_TS::timestamp_ntz(0) as EVENT_TS,
        rpad(EVENT_TYPE, 12, ' ')::varchar(12) as EVENT_TYPE,
        left(DETAILS, 160)::varchar(160) as DETAILS
    from {{ source_relation }}
    where EVENT_TS < dateadd(day, -{{ archive_days }}, convert_timezone('UTC', current_timestamp())::date)
),
occurrences as (
    select *, row_number() over (
        partition by ACTOR_USER_ID, DOCUMENT_ID, EVENT_TS, EVENT_TYPE, DETAILS order by EVENT_ID) as OCCURRENCE
    from eligible
),
{% if is_incremental() %}
archived as (
    select ACTOR_USER_ID, DOCUMENT_ID, EVENT_TS, EVENT_TYPE, DETAILS, count(*) as ARCHIVED_COUNT
    from {{ this }}
    group by ACTOR_USER_ID, DOCUMENT_ID, EVENT_TS, EVENT_TYPE, DETAILS
),
next_id as (
    select coalesce(max(ARCHIVE_ID) + 1, {{ sequence_start }}) as NEXT_ID from {{ this }}
),
pending as (
    select o.*
    from occurrences o
    left join archived a
        on equal_null(o.ACTOR_USER_ID, a.ACTOR_USER_ID) and equal_null(o.DOCUMENT_ID, a.DOCUMENT_ID)
        and equal_null(o.EVENT_TS, a.EVENT_TS) and equal_null(o.EVENT_TYPE, a.EVENT_TYPE)
        and equal_null(o.DETAILS, a.DETAILS)
    where o.OCCURRENCE > coalesce(a.ARCHIVED_COUNT, 0)
)
{% else %}
next_id as (
    select {{ sequence_start }} as NEXT_ID
),
pending as (
    select * from occurrences
)
{% endif %}
select
    (n.NEXT_ID - 1 + row_number() over (order by p.EVENT_ID))::number(38,0) as ARCHIVE_ID,
    p.ACTOR_USER_ID,
    p.DOCUMENT_ID,
    p.EVENT_TS,
    p.EVENT_TYPE,
    p.DETAILS
from pending p
cross join next_id n
{% endmacro %}
