-- Replaces SSIS pkg_auth_users: auth_users.csv -> DER Normalise timestamps -> stg.stg_auth_users.
-- The package truncates and reloads the whole file; it does not read the business date.
-- extracted_at mirrors @[System::StartTime], the Eastern legacy server clock.
with extract as (
    select * from {{ source('pkg_auth_users', 'EXT_AUTH_USERS') }}
)

select
    nullif("ID", '')::varchar(36) as id,
    nullif("EMAIL", '')::varchar(255) as email,
    nullif("DISPLAY_NAME", '')::varchar(100) as display_name,
    "EMAIL_VERIFIED" = 't' as email_verified,
    "MFA_ENABLED" = 't' as mfa_enabled,
    to_timestamp_ntz(replace(nullif("CREATED_AT", ''), '+00', ''), 'YYYY-MM-DD HH24:MI:SS.FF') as created_at,
    to_timestamp_ntz(replace(nullif("UPDATED_AT", ''), '+00', ''), 'YYYY-MM-DD HH24:MI:SS.FF') as updated_at,
    to_timestamp_ntz(replace(nullif("LAST_LOGIN_AT", ''), '+00', ''), 'YYYY-MM-DD HH24:MI:SS.FF') as last_login_at,
    lower(substr(nullif("EMAIL", ''), position('@', nullif("EMAIL", '')) + 1, 255))::varchar(255) as email_domain,
    convert_timezone('America/New_York', current_timestamp())::timestamp_ntz as extracted_at,
    'auth-service'::varchar(40) as source_system
from extract
