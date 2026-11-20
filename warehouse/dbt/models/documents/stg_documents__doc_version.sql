{{ config(materialized='view') }}
select * from {{ source('documents_converted', 'STG_DOC_VERSION') }}
