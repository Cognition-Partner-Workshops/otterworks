{{ config(materialized='view') }}
select * from {{ ref('dbc_qrylog') }}
