-- The package strips "+00" instead of converting the offset, which is only right for UTC values.
-- Any timestamp with another offset (or none) would be stored as the wrong instant.
select e."ID", e."CREATED_AT", e."UPDATED_AT", e."LAST_LOGIN_AT"
from {{ source('pkg_auth_users', 'EXT_AUTH_USERS') }} as e
inner join {{ ref('stg_auth_users') }} as s on s.id = e."ID"
where not endswith(e."CREATED_AT", '+00')
   or not endswith(e."UPDATED_AT", '+00')
   or (e."LAST_LOGIN_AT" != '' and not endswith(e."LAST_LOGIN_AT", '+00'))
