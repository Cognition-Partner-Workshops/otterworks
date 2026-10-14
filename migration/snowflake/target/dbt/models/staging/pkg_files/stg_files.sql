-- Port of SSIS package pkg_files (files.csv -> stg.stg_files).
-- The flat-file source turns empty fields into NULL; DER Normalise timestamps casts the flags and
-- strips T/Z from the UTC timestamps; LKP Tenant from workspace adds tenant_id (no match -> NULL);
-- the Script Task "SCR Convert sizes to MB" sets size_mb = ROUND(size_bytes / 1048576.0, 3).
with files as (

    select
        nullif(ID, '') as id,
        nullif(NAME, '') as name,
        nullif(MIME_TYPE, '') as mime_type,
        nullif(SIZE_BYTES, '') as size_bytes,
        nullif(FOLDER_ID, '') as folder_id,
        nullif(OWNER_ID, '') as owner_id,
        nullif(WORKSPACE_ID, '') as workspace_id,
        nullif(VERSION, '') as version,
        nullif(IS_TRASHED, '') as is_trashed,
        nullif(ARCHIVED, '') as archived,
        nullif(CREATED_AT, '') as created_at,
        nullif(UPDATED_AT, '') as updated_at
    from {{ source('pkg_files', 'EXT_FILES') }}

),

workspace_tenants as (

    -- Lookup reference: SELECT DISTINCT workspace_id, tenant_id FROM stg.stg_auth_workspace_members.
    -- The cache keeps one tenant per workspace; tests/pkg_files__workspace_single_tenant.sql
    -- guards that there is only ever one.
    select
        "workspace_id"::varchar as workspace_id,
        max("tenant_id")::varchar as tenant_id
    from {{ source('raw', 'STG_AUTH_WORKSPACE_MEMBERS') }}
    where "workspace_id" is not null
    group by 1

)

select
    f.id::varchar(36) as id,
    f.name::varchar(500) as name,
    f.mime_type::varchar(100) as mime_type,
    f.size_bytes::number(19, 0) as size_bytes,
    f.folder_id::varchar(36) as folder_id,
    f.owner_id::varchar(36) as owner_id,
    f.workspace_id::varchar(36) as workspace_id,
    f.version::number(10, 0) as version,
    coalesce(f.is_trashed = 'true', false)::boolean as is_trashed,
    (f.archived = 'true')::boolean as archived,
    replace(replace(f.created_at, 'T', ' '), 'Z', '')::timestamp_ntz(7) as created_at,
    replace(replace(f.updated_at, 'T', ' '), 'Z', '')::timestamp_ntz(7) as updated_at,
    -- ROUND(size_bytes / 1048576.0, 3), half away from zero, in exact integer arithmetic.
    (floor((f.size_bytes::number(19, 0) * 1000 + 524288) / 1048576) / 1000)::number(18, 3) as size_mb,
    t.tenant_id::varchar(36) as tenant_id,
    -- @[System::StartTime]: the package start on the server's Eastern clock.
    convert_timezone('America/New_York', current_timestamp())::timestamp_ntz(7) as extracted_at,
    'file-service'::varchar(40) as source_system
from files as f
left join workspace_tenants as t
    on t.workspace_id = f.workspace_id
