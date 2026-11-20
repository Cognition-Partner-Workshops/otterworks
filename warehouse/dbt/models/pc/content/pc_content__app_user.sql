{{ config(materialized='incremental', incremental_strategy='merge', unique_key='USER_ID') }}
select
    USER_ID,
    cast(DISPLAY_NAME as varchar(200)) as DISPLAY_NAME,
    cast(left(EMAIL, 120) as varchar(120)) as EMAIL,
    cast(left(STATUS_CD, 12) as varchar(12)) as STATUS_CD,
    CREATED_DT
from {{ ref('pc_content__stg_app_user') }}
