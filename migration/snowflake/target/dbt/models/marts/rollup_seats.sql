select
    {{ business_date() }} as business_date,
    tenants.tenant_id,
    tenants.plan_id,
    tenants.plan_tier,
    count(*) as seat_count
from {{ ref('dim_user') }} as users
join {{ source('raw', 'STG_AUTH_WORKSPACE_MEMBERS') }} as members
    on members."user_id" = users.user_id
join {{ ref('dim_tenant') }} as tenants
    on tenants.tenant_id = members."tenant_id"
where members."joined_at" < dateadd(day, 1, {{ business_date() }})
group by tenants.tenant_id, tenants.plan_id, tenants.plan_tier
