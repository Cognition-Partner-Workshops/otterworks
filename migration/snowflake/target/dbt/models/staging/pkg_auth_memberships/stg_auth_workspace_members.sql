-- Replaces SSIS pkg_auth_memberships: truncate stg.stg_auth_workspace_members, then load
-- auth_workspace_members.csv with Derived Column "DER Normalise timestamps":
--   joined_at     = (DT_DBTIMESTAMP2,7) REPLACE(joined_at, "+00", "")
--   extracted_at  = @[System::StartTime] (one value per run: dbt run_started_at, on the US Eastern clock)
--   source_system = "auth-service"
-- No lookups, filters or Script Task; every row of the file lands.
select
    user_id::varchar(36) as user_id,
    workspace_id::varchar(36) as workspace_id,
    workspace_name::varchar(200) as workspace_name,
    tenant_id::varchar(36) as tenant_id,
    role::varchar(50) as role,
    to_timestamp_ntz(replace(joined_at, '+00', ''), 'YYYY-MM-DD HH24:MI:SS.FF') as joined_at,
    convert_timezone(
        'UTC',
        'America/New_York',
        '{{ run_started_at.strftime("%Y-%m-%d %H:%M:%S.%f") }}'::timestamp_ntz
    ) as extracted_at,
    'auth-service'::varchar(40) as source_system
from {{ source('pkg_auth_memberships', 'EXT_AUTH_WORKSPACE_MEMBERS') }}
