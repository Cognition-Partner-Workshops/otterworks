{{ config(materialized='view') }}
select * from {{ ref('pc_content__stg_app_user') }}
