{{ config(materialized='view') }}
select * from {{ source('documents_converted', 'FOLDER') }}
