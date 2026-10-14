-- The legacy cursor writes one row per dim_tenant row; every tenant must appear for every built date.
select dates.business_date, tenants.tenant_id
from (select distinct business_date from {{ ref('build_mart_tenant_usage') }}) as dates
cross join {{ ref('dim_tenant') }} as tenants
left join {{ ref('build_mart_tenant_usage') }} as mart
    on mart.business_date = dates.business_date
   and mart.tenant_id = tenants.tenant_id
where mart.tenant_id is null
