-- email_domain is everything after the first @, lowercased; an address without @ keeps
-- the whole lowercased address (FINDSTRING returns 0). Warn when that fallback fires.
{{ config(severity='warn') }}
select id, email, email_domain
from {{ ref('stg_auth_users') }}
where position('@', email) = 0
