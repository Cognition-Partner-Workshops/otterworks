with memberships as (
    select "user_id" as user_id, min("tenant_id") as tenant_id
    from {{ source('raw', 'STG_AUTH_WORKSPACE_MEMBERS') }}
    group by "user_id"
)

select
    users."id" as user_id,
    memberships.tenant_id,
    users."email" as email,
    users."email_domain" as email_domain,
    users."display_name" as display_name,
    iff(lower(users."email_verified"::varchar) in ('1', 'true', 't', 'yes', 'y'), 1, 0) as email_verified,
    iff(lower(users."mfa_enabled"::varchar) in ('1', 'true', 't', 'yes', 'y'), 1, 0) as mfa_enabled,
    users."created_at" as created_at_utc,
    users."last_login_at" as last_login_utc
from {{ source('raw', 'STG_AUTH_USERS') }} as users
left join memberships
    on memberships.user_id = users."id"
where users."created_at" < dateadd(day, 1, {{ business_date() }})
