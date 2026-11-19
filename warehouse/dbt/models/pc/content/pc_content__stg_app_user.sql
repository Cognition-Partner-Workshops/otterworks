{{ config(materialized='table') }}
select
    cast(USER_ID as bigint) as USER_ID,
    cast(left(trim(DISPLAY_NAME, ' '), 200) as varchar(200)) as DISPLAY_NAME,
    cast(left(lower(trim(EMAIL, ' ')), 200) as varchar(200)) as EMAIL,
    cast(left(upper(trim(STATUS_CD, ' ')), 200) as varchar(200)) as STATUS_CD,
    cast(CREATED_DT as date) as CREATED_DT
from {{ source('pc_content_src', 'APP_USER') }}
