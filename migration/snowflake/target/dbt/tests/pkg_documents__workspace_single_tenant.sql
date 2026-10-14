-- pkg_documents' tenant Lookup keys on workspace_id; a workspace with two tenants would make
-- the SSIS Lookup pick an arbitrary one, so the model assumes there are none.
select "workspace_id", count(distinct "tenant_id") as tenants
from {{ source('raw', 'STG_AUTH_WORKSPACE_MEMBERS') }}
group by 1
having count(distinct "tenant_id") > 1
