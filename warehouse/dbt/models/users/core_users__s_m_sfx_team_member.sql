{{ config(materialized='view') }}
select * from {{ ref('pc_content__team_member') }}
