-- tenant_id is the lowest tenant among the user's workspace memberships, NULL only without one.
with expected as (
    select "user_id" as user_id, min("tenant_id") as tenant_id
    from {{ source('raw', 'STG_AUTH_WORKSPACE_MEMBERS') }}
    group by "user_id"
)

select audit.audit_id, audit.tenant_id, expected.tenant_id as expected_tenant_id
from {{ ref('stg_audit_events') }} as audit
left join expected on audit.user_id = expected.user_id
where not equal_null(audit.tenant_id, expected.tenant_id)
