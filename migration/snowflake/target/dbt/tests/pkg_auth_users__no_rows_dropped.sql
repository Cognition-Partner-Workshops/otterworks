-- pkg_auth_users has no filter, lookup or split: every extract row lands in staging once.
select extract_rows, staging_rows
from (
    select
        (select count(*) from {{ source('pkg_auth_users', 'EXT_AUTH_USERS') }}) as extract_rows,
        (select count(*) from {{ ref('stg_auth_users') }}) as staging_rows
)
where extract_rows != staging_rows
