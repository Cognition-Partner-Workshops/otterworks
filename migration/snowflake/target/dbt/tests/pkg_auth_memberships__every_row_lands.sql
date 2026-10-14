-- The package has no lookup, split or filter: the staging model has exactly the file's rows.
select extract_rows, staging_rows
from (
    select
        (select count(*) from {{ source('pkg_auth_memberships', 'EXT_AUTH_WORKSPACE_MEMBERS') }})
            as extract_rows,
        (select count(*) from {{ ref('stg_auth_workspace_members') }}) as staging_rows
)
where extract_rows != staging_rows
