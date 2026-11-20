{{ config(materialized='table', post_hook=[]) }}
{% set sequence_start = var('pc_audit_summary_sequence_start', 50001) | int %}

with grouped as (
    select EVENT_TS::date as SUMMARY_DT,
           CUSTOMER_ID::number(38,0) as CUSTOMER_ID,
           count(EVENT_ID) as EVENT_COUNT,
           sum(iff(rtrim(EVENT_TYPE, ' ') = 'DOC_EXPORT', 1, 0)) as EXPORT_COUNT
    from {{ ref('pc_audit__audit_event') }}
    group by 1, 2
)
select
    ({{ sequence_start }} - 1 + row_number() over (
        order by SUMMARY_DT, CUSTOMER_ID nulls first
    ))::number(38,0) as SUMMARY_ID,
    SUMMARY_DT::date as SUMMARY_DT,
    CUSTOMER_ID::number(38,0) as CUSTOMER_ID,
    EVENT_COUNT::number(38,0) as EVENT_COUNT,
    EXPORT_COUNT::number(38,0) as EXPORT_COUNT
from grouped
