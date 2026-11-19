{{ config(materialized='view') }}
select * from {{ source('documents_converted', 'STG_STORAGE_USAGE_DAILY') }}
