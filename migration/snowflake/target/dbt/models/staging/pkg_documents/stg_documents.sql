-- Replaces SSIS pkg_documents: documents.csv -> stg.stg_documents.
-- Empty flat-file fields arrive as NULL in the package, so every column goes through nullif(.., '').
with documents as (
    select
        nullif(ID, '') as id,
        nullif(TITLE, '') as title,
        nullif(CONTENT_TYPE, '') as content_type,
        nullif(OWNER_ID, '') as owner_id,
        nullif(FOLDER_ID, '') as folder_id,
        nullif(WORKSPACE_ID, '') as workspace_id,
        nullif(IS_DELETED, '') as is_deleted,
        nullif(IS_TEMPLATE, '') as is_template,
        nullif(ARCHIVED, '') as archived,
        nullif(WORD_COUNT, '') as word_count,
        nullif(VERSION, '') as version,
        nullif(CREATED_AT, '') as created_at,
        nullif(UPDATED_AT, '') as updated_at
    from {{ source('pkg_documents', 'EXT_DOCUMENTS') }}
),

-- LKP Tenant from workspace: SELECT DISTINCT workspace_id, tenant_id FROM stg.stg_auth_workspace_members.
-- No-match rows are kept with a NULL tenant_id; one tenant per workspace is asserted by
-- tests/pkg_documents__workspace_single_tenant.sql.
workspace_tenants as (
    select
        "workspace_id"::varchar as workspace_id,
        max("tenant_id")::varchar as tenant_id
    from {{ source('raw', 'STG_AUTH_WORKSPACE_MEMBERS') }}
    group by 1
)

select
    d.id::varchar(36) as id,
    d.title::varchar(500) as title,
    d.content_type::varchar(50) as content_type,
    d.owner_id::varchar(36) as owner_id,
    d.folder_id::varchar(36) as folder_id,
    d.workspace_id::varchar(36) as workspace_id,
    coalesce(d.is_deleted = 't', false) as is_deleted,
    coalesce(d.is_template = 't', false) as is_template,
    case when d.archived is null then null else d.archived = 't' end as archived,
    d.word_count::integer as word_count,
    d.version::integer as version,
    replace(d.created_at, '+00', '')::timestamp_ntz(7) as created_at,
    replace(d.updated_at, '+00', '')::timestamp_ntz(7) as updated_at,
    w.tenant_id::varchar(36) as tenant_id,
    '{{ run_started_at.strftime("%Y-%m-%d %H:%M:%S.%f") }}'::timestamp_ntz as extracted_at,
    'document-service'::varchar(40) as source_system
from documents as d
left join workspace_tenants as w
    on w.workspace_id = d.workspace_id
