{{ config(severity='warn') }}
-- (DT_BOOL)(x == "t") turns every value other than lowercase t into false, including
-- 'true', 'T', '1' and empty. Warn when the extract carries such a value.
select e."ID", e."EMAIL_VERIFIED", e."MFA_ENABLED", s.email_verified, s.mfa_enabled
from {{ source('pkg_auth_users', 'EXT_AUTH_USERS') }} as e
inner join {{ ref('stg_auth_users') }} as s on s.id = e."ID"
where e."EMAIL_VERIFIED" not in ('t', 'f') or e."MFA_ENABLED" not in ('t', 'f')
