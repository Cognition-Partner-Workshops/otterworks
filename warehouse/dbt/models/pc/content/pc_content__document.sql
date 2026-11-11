-- m_SFX_DOCUMENT: STG_DOCUMENT -> EXP_OWNER_CHECK (:LKP.LKP_APP_USER_STATUS(OWNER_USER_ID))
-- -> FIL_KNOWN_OWNER (NOT ISNULL(o_OWNER_STATUS)) -> LKP_DOCUMENT -> UPD_DOCUMENT.
-- The unconnected lookup reads APP_USER on USER_ID with Use First Value. The runner orders
-- the cache by USER_ID; APP_USER.USER_ID is the primary key, so the first match is the only match.
-- A NULL owner id, an unknown owner or a NULL owner status all make the filter drop the row.
-- IIF(ISNULL(lkp_DOCUMENT_ID), DD_INSERT, DD_UPDATE) becomes a MERGE on DOCUMENT_ID.
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
