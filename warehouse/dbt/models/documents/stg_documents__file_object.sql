{{ config(materialized='view') }}
select * from {{ source('documents_converted', 'STG_FILE_OBJECT') }}
