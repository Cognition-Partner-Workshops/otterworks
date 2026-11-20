{{ config(materialized='table', alias='spark__lake_compaction_documents') }}
select * from {{ ref('docs_event_export_hourly') }}
