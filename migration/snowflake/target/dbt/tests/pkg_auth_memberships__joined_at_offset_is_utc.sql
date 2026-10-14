-- REPLACE(joined_at,"+00","") only loses nothing while every value carries exactly one
-- trailing +00. Any other offset would land shifted (or fail the cast), so flag it.
select joined_at
from {{ source('pkg_auth_memberships', 'EXT_AUTH_WORKSPACE_MEMBERS') }}
where not regexp_like(joined_at, '\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}(\\.\\d{1,7})?\\+00')
