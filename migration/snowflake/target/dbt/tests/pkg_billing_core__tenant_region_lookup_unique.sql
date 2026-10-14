-- LKP Tenant region must find at most one region row per tenant: the replay keeps one row per
-- tenant_id from billing_tenant_regions.csv and the model keeps the lowest region_code, which
-- only agree while the reference file has no duplicated tenant_id.
select r.tenant_id, count(*) as region_rows
from {{ source('pkg_billing_core', 'EXT_BILLING_TENANT_REGIONS') }} as r
inner join {{ ref('stg_billing_tenants') }} as t
    on t.id = r.tenant_id
group by r.tenant_id
having count(*) > 1
