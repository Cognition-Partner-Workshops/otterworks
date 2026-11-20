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
    from {{ source('users_converted', 'ROLE_GRANT') }}
    qualify row_number() over (
        partition by USER_ID
        order by case left(upper(trim(ROLE_CD, ' ')), 12)
            when 'ADMIN' then 2 when 'EDITOR' then 1 else 0 end desc
    ) = 1
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
