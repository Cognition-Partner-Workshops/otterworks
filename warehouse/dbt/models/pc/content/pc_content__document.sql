{{ config(materialized='incremental', incremental_strategy='merge', unique_key='DOCUMENT_ID', on_schema_change='append_new_columns') }}
with owner_status as (
    select USER_ID, STATUS_CD
    from {{ ref('pc_content__app_user') }}
    qualify row_number() over (partition by USER_ID order by USER_ID) = 1
)
select
    s.DOCUMENT_ID,
    s.FOLDER_ID,
    s.OWNER_USER_ID,
    s.CUSTOMER_ID,
    cast(left(s.DOCUMENT_NAME, 120) as varchar(120)) as DOCUMENT_NAME,
    s.CREATED_DT,
    cast(left(s.STATUS_CD, 12) as varchar(12)) as STATUS_CD,
    cast(left(s.FILE_TYPE, 8) as varchar(8)) as FILE_TYPE
from {{ ref('pc_content__stg_document') }} s
join owner_status o on o.USER_ID = s.OWNER_USER_ID
where o.STATUS_CD is not null
