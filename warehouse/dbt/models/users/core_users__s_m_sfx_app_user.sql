{{ config(materialized='view') }}
select * from {{ ref('pc_content__app_user') }}
