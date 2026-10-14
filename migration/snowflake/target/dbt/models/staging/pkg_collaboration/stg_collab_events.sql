-- Replaces SSIS pkg_collaboration: collab_events.csv -> stg.stg_collab_events (truncate + full reload).
-- Empty flat-file fields arrive as NULL in the package, so every column goes through nullif(.., '').
with collab_events as (
    select
        nullif(ID, '') as id,
        nullif(EVENT_TYPE, '') as event_type,
        nullif(DOCUMENT_ID, '') as document_id,
        nullif(USER_ID, '') as user_id,
        nullif(SESSION_ID, '') as session_id,
        nullif(CREATED_AT, '') as created_at
    from {{ source('pkg_collaboration', 'EXT_COLLAB_EVENTS') }}
),

-- LKP Tenant from document: SELECT id AS document_id, tenant_id FROM stg.stg_documents.
-- No-match rows are kept with a NULL tenant_id; stg_documents.id is unique, so the join cannot fan out.
document_tenants as (
    select
        "id"::varchar as document_id,
        "tenant_id"::varchar as tenant_id
    from {{ source('raw', 'STG_DOCUMENTS') }}
)

select
    e.id::varchar(36) as id,
    e.event_type::varchar(30) as event_type,
    e.document_id::varchar(36) as document_id,
    e.user_id::varchar(36) as user_id,
    e.session_id::varchar(36) as session_id,
    replace(e.created_at, '+00', '')::timestamp_ntz(7) as created_at,
    d.tenant_id::varchar(36) as tenant_id,
    '{{ run_started_at.strftime("%Y-%m-%d %H:%M:%S.%f") }}'::timestamp_ntz as extracted_at,
    'collab-service'::varchar(40) as source_system
from collab_events as e
left join document_tenants as d
    on d.document_id = e.document_id
