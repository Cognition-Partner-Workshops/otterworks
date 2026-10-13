{{ config(
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="business_date"
) }}

select
    f.business_date,
    f.tenant_id,
    t.tenant_name,
    t.plan_tier,
    f.bytes_used,
    f.included_bytes,
    r.overage_gb,
    p.overage_cents_per_gb,
    r.overage_cents
from {{ ref("rollup_storage_daily") }} as f
inner join {{ ref("dim_tenant") }} as t
    on t.tenant_id = f.tenant_id
inner join {{ ref("dim_plan") }} as p
    on p.plan_id = f.plan_id
inner join {{ ref("rate_overage") }} as r
    on r.business_date = f.business_date
   and r.tenant_id = f.tenant_id
where f.business_date = {{ business_date() }}
  and r.overage_gb is not null
