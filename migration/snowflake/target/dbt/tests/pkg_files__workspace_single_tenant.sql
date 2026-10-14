-- LKP Tenant from workspace caches one tenant per workspace; a workspace with two tenants
-- would make stg_files.tenant_id depend on cache order.
select "workspace_id", count(distinct "tenant_id") as tenants
from {{ source('raw', 'STG_AUTH_WORKSPACE_MEMBERS') }}
group by 1
having count(distinct "tenant_id") > 1
