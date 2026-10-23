select
    "workspace_id" as workspace_id,
    max("workspace_name") as workspace_name,
    max("tenant_id") as tenant_id,
    count(*) as member_count
from {{ source('raw', 'STG_AUTH_WORKSPACE_MEMBERS') }}
where "joined_at" < dateadd(day, 1, {{ business_date() }})
group by "workspace_id"
