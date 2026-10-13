-- dbo.usp_rollup_seats: seats in use per tenant for the business date.
--
-- The legacy procedure joins dim_user to every workspace membership row and COUNT(*)s, so a user
-- who belongs to two workspaces of the same tenant is counted as two seats. The seat reports,
-- plan limits and the plan-tier summary have always shown that number. This model counts each
-- user once per tenant. Set the var legacy_seats_count_workspace_memberships to true to reproduce
-- the legacy count exactly while the data owners decide (gate/out/ledger.md, rollup_seats).
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='business_date') }}

{%- set legacy_memberships = var('legacy_seats_count_workspace_memberships', false) %}

select
    {{ business_date() }} as business_date,
    tenants.tenant_id,
    tenants.plan_id,
    tenants.plan_tier,
    {% if legacy_memberships -%}
    count(*)
    {%- else -%}
    count(distinct users.user_id)
    {%- endif %} as seat_count,
    current_timestamp()::timestamp_ntz as loaded_at
from {{ ref('dim_user') }} as users
inner join {{ ref('stg_auth_workspace_members') }} as members
    on members.user_id = users.user_id
inner join {{ ref('dim_tenant') }} as tenants
    on tenants.tenant_id = members.tenant_id
where members.joined_at < dateadd(day, 1, {{ business_date() }})
group by tenants.tenant_id, tenants.plan_id, tenants.plan_tier
