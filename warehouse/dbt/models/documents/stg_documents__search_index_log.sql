{{ config(materialized='view') }}

select * from {{ source('documents_converted', 'STG_SEARCH_INDEX_LOG') }}
