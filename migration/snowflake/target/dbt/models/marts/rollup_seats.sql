{{ config(
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="business_date"
) }}

select
    {{ business_date() }} as business_date,
    t.tenant_id,
    t.plan_id,
    t.plan_tier,
    count(*) as seat_count,
    cast(null as integer) as seat_limit,
    cast(null as integer) as over_limit,
    current_timestamp() as loaded_at
from {{ ref("dim_user") }} as u
inner join {{ source("raw", "STG_AUTH_WORKSPACE_MEMBERS") }} as m
    on m."user_id" = u.user_id
inner join {{ ref("dim_tenant") }} as t
    on t.tenant_id = m."tenant_id"
where m."joined_at" < dateadd(day, 1, {{ business_date() }})
group by
    t.tenant_id,
    t.plan_id,
    t.plan_tier
