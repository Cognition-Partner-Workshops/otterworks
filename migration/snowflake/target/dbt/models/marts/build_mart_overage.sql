-- dbo.usp_build_mart_overage: storage overage charges per tenant for billing and the overage
-- reports (rpt_overage_charges, rpt_overage_by_tier, rpt_storage_vs_included).
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='business_date') }}

select
    overage.business_date,
    overage.tenant_id,
    tenants.tenant_name,
    tenants.plan_tier,
    overage.bytes_used,
    overage.included_bytes,
    overage.overage_gb,
    plans.overage_cents_per_gb,
    overage.overage_cents,
    current_timestamp()::timestamp_ntz as loaded_at
from {{ ref('rate_overage') }} as overage
inner join {{ ref('dim_tenant') }} as tenants
    on tenants.tenant_id = overage.tenant_id
inner join {{ ref('dim_plan') }} as plans
    on plans.plan_id = overage.plan_id
where {{ for_business_date('overage.business_date') }}
  and overage.overage_gb is not null
