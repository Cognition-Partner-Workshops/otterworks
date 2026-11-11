-- m_SFX_DOC_SHARE: FF_DOC_SHARE -> EXP_DOC_SHARE -> LKP_ROLE_GRANT -> EXP_ACCESS_LEVEL -> DOC_SHARE.
-- The session treats source rows as update with update else insert, so this is a MERGE on SHARE_ID.
--
-- LKP_ROLE_GRANT reads SFX_USERS.ROLE_GRANT on USER_ID with Use First Value. That table is
-- loaded by m_SFX_ROLE_GRANT, which another effort owns, so the lookup source is rebuilt here
-- from the same landing file with the same expression: UPPER(LTRIM(RTRIM(ROLE_CD))) into CHAR(12).
-- The runner builds the cache with ORDER BY USER_ID and keeps load order for ties. The load
-- order is GRANT_ID order, so the first match is the lowest GRANT_ID for each user.
--
-- DECODE(TRUE, ...) treats a NULL condition as false. A user with no grant falls through to
-- ACCESS_LEVEL. CASE has the same NULL rule.
{{ config(materialized='incremental', incremental_strategy='merge', unique_key='SHARE_ID') }}
with src as (
    select
        cast(SHARE_ID as bigint) as SHARE_ID,
        cast(DOCUMENT_ID as bigint) as DOCUMENT_ID,
        cast(USER_ID as bigint) as USER_ID,
        upper(trim(ACCESS_LEVEL, ' ')) as ACCESS_LEVEL,
        cast(SHARED_DT as date) as SHARED_DT
    from {{ source('pc_content_src', 'DOC_SHARE') }}
),
role_grant as (
    select
        cast(USER_ID as bigint) as USER_ID,
        left(upper(trim(ROLE_CD, ' ')), 12) as ROLE_CD
    from {{ source('pc_content_src', 'ROLE_GRANT') }}
    qualify row_number() over (partition by cast(USER_ID as bigint) order by GRANT_ID) = 1
)
select
    s.SHARE_ID,
    s.DOCUMENT_ID,
    s.USER_ID,
    cast(left(case
        when r.ROLE_CD = 'ADMIN' then 'OWNER'
        when r.ROLE_CD = 'EDITOR' and s.ACCESS_LEVEL = 'VIEW' then 'EDIT'
        else s.ACCESS_LEVEL
    end, 12) as varchar(12)) as ACCESS_LEVEL,
    s.SHARED_DT
from src s
left join role_grant r on r.USER_ID = s.USER_ID
