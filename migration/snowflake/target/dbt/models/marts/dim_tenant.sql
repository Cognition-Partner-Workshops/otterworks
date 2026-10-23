with tenants as (
    select
        "id" as tenant_id,
        "name" as tenant_name,
        "status" as status,
        iff(lower("tax_exempt"::varchar) in ('1', 'true', 't', 'yes', 'y'), 1, 0) as tax_exempt,
        "region_code" as region_code
    from {{ source('raw', 'STG_BILLING_TENANTS') }}
),
current_subscriptions as (
    select
        "tenant_id" as tenant_id,
        "plan_id" as plan_id,
        "status" as subscription_status,
        row_number() over (
            partition by "tenant_id"
            order by "starts_on" desc, "id" desc
        ) as subscription_rank
    from {{ source('raw', 'STG_BILLING_SUBSCRIPTIONS') }}
    where "starts_on" <= {{ business_date() }}
      and ("ends_on" is null or "ends_on" >= {{ business_date() }})
)

select
    tenants.tenant_id,
    tenants.tenant_name,
    tenants.status,
    tenants.tax_exempt,
    tenants.region_code,
    subscriptions.plan_id,
    plans.plan_tier,
    subscriptions.subscription_status
from tenants
left join current_subscriptions as subscriptions
    on subscriptions.tenant_id = tenants.tenant_id
   and subscriptions.subscription_rank = 1
left join {{ ref('dim_plan') }} as plans
    on plans.plan_id = subscriptions.plan_id
