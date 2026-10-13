-- pkg_billing_core, DFT Load stg_billing_tenants: billing_tenants.csv -> stg.stg_billing_tenants.
-- LKP Tenant region reads billing_tenant_regions.csv on id = tenant_id; no match leaves region_code NULL.
with tenants as (
    select * from {{ source('pkg_billing_core', 'EXT_BILLING_TENANTS') }}
),

regions as (
    select
        tenant_id,
        nullif(region_code, '') as region_code
    from {{ source('pkg_billing_core', 'EXT_BILLING_TENANT_REGIONS') }}
    where nullif(tenant_id, '') is not null
    qualify row_number() over (partition by tenant_id order by region_code) = 1
)

select
    nullif(t.id, '')::varchar(36) as id,
    nullif(t.name, '')::varchar(200) as name,
    -- (DT_BOOL)(tax_exempt == "t"): case-sensitive, a blank flag is not exempt
    coalesce(nullif(t.tax_exempt, '') = 't', false) as tax_exempt,
    nullif(t.status, '')::varchar(20) as status,
    r.region_code::varchar(20) as region_code,
    convert_timezone('America/New_York', current_timestamp())::timestamp_ntz as extracted_at,
    'legacy-billing'::varchar(40) as source_system
from tenants as t
left join regions as r
    on r.tenant_id = nullif(t.id, '')
