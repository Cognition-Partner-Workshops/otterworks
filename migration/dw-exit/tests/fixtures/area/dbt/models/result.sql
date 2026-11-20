{{ config(materialized='table') }}
select * from {{ source('fixture', 'STG_T') }}
