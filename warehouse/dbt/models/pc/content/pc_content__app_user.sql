-- m_SFX_APP_USER: STG_APP_USER -> LKP_APP_USER (target, Use First Value) -> UPD_APP_USER.
-- IIF(ISNULL(lkp_USER_ID), DD_INSERT, DD_UPDATE) is an upsert on the target key,
-- so it becomes an incremental MERGE on USER_ID. Reruns update rows in place.
{{ config(materialized='incremental', incremental_strategy='merge', unique_key='USER_ID') }}
select
    USER_ID,
    cast(left(DISPLAY_NAME, 60) as varchar(60)) as DISPLAY_NAME,
    cast(left(EMAIL, 120) as varchar(120)) as EMAIL,
    cast(left(STATUS_CD, 12) as varchar(12)) as STATUS_CD,
    CREATED_DT
from {{ ref('pc_content__stg_app_user') }}
