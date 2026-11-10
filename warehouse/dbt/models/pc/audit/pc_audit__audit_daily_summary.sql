{#- SEQ_AUDIT_SUMMARY Current Value 50001 (m_SFX_AUDIT_DAILY_SUMMARY.XML). The runner numbers aggregator groups in
    first-seen read order, which is EVENT_ID order for the audit target, so new groups are ranked by MIN(EVENT_ID).
    Existing groups keep their SUMMARY_ID: replay is idempotent instead of the legacy duplicate append. -#}
{% set sequence_start = var('pc_audit_summary_sequence_start', 50001) | int %}
{{ config(materialized='incremental', incremental_strategy='merge', unique_key='SUMMARY_ID', full_refresh=false) }}

with grouped as (
    select
        EVENT_TS::date as SUMMARY_DT,
        CUSTOMER_ID::number(38,0) as CUSTOMER_ID,
        count(EVENT_ID) as EVENT_COUNT,
        sum(iff(rtrim(EVENT_TYPE, ' ') = 'DOC_EXPORT', 1, 0)) as EXPORT_COUNT,
        min(EVENT_ID) as FIRST_EVENT_ID
    from {{ ref('pc_audit__audit_event') }}
    group by 1, 2
),
{% if is_incremental() %}
existing as (
    select SUMMARY_ID, SUMMARY_DT, CUSTOMER_ID from {{ this }}
),
next_id as (
    select coalesce(max(SUMMARY_ID) + 1, {{ sequence_start }}) as NEXT_ID from {{ this }}
),
matched as (
    select e.SUMMARY_ID, g.SUMMARY_DT, g.CUSTOMER_ID, g.EVENT_COUNT, g.EXPORT_COUNT
    from grouped g
    join existing e on equal_null(g.SUMMARY_DT, e.SUMMARY_DT) and equal_null(g.CUSTOMER_ID, e.CUSTOMER_ID)
),
unmatched as (
    select g.*
    from grouped g
    where not exists (select 1 from existing e
                      where equal_null(g.SUMMARY_DT, e.SUMMARY_DT) and equal_null(g.CUSTOMER_ID, e.CUSTOMER_ID))
),
{% else %}
next_id as (
    select {{ sequence_start }} as NEXT_ID
),
unmatched as (
    select * from grouped
),
{% endif %}
numbered as (
    select n.NEXT_ID - 1 + row_number() over (order by u.FIRST_EVENT_ID) as SUMMARY_ID,
           u.SUMMARY_DT, u.CUSTOMER_ID, u.EVENT_COUNT, u.EXPORT_COUNT
    from unmatched u
    cross join next_id n
    {% if is_incremental() %}
    union all
    select * from matched
    {% endif %}
)
select
    SUMMARY_ID::number(38,0) as SUMMARY_ID,
    SUMMARY_DT::date as SUMMARY_DT,
    CUSTOMER_ID::number(38,0) as CUSTOMER_ID,
    EVENT_COUNT::number(38,0) as EVENT_COUNT,
    EXPORT_COUNT::number(38,0) as EXPORT_COUNT
from numbered
