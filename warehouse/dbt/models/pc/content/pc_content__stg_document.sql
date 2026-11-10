-- m_SFX_STG_DOCUMENT: FF_DOCUMENT -> EXP_DOCUMENT -> STG_DOCUMENT (truncate and load).
{{ config(materialized='table') }}
select
    cast(DOCUMENT_ID as bigint) as DOCUMENT_ID,
    cast(FOLDER_ID as bigint) as FOLDER_ID,
    cast(OWNER_USER_ID as bigint) as OWNER_USER_ID,
    cast(CUSTOMER_ID as bigint) as CUSTOMER_ID,
    cast(left(trim(DOCUMENT_NAME, ' '), 200) as varchar(200)) as DOCUMENT_NAME,
    cast(CREATED_DT as date) as CREATED_DT,
    cast(left(upper(trim(STATUS_CD, ' ')), 200) as varchar(200)) as STATUS_CD
from {{ source('pc_content_src', 'DOCUMENT') }}
