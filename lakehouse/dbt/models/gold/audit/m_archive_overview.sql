{{ config(materialized='view') }}
select event_type, count(*) as event_count
from {{ ref('audit_event_archive') }} group by event_type
