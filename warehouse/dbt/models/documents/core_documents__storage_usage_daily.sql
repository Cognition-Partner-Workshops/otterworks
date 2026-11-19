{{ config(materialized='view') }}
select * from {{ source('documents_converted', 'STORAGE_USAGE_DAILY') }}
