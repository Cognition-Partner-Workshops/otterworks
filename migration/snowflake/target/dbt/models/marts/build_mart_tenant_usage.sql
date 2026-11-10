-- One row for every tenant, with zeros where the tenant had no activity that day.
with usage as (
    select
        tenant_id,
        sum(iff(event_kind = 'api', units, 0)) as api_units,
        sum(iff(event_kind = 'compute', units, 0)) as compute_units
    from {{ ref('rollup_usage_events') }}
    group by tenant_id
),

active_users as (
    select tenant_id, count(distinct user_id) as active_users
    from {{ ref('rollup_audit') }}
    group by tenant_id
),

documents as (
    select tenant_id, count(*) as document_count
    from {{ ref('dim_document') }}
    where is_deleted = 0
    group by tenant_id
),

files as (
    select tenant_id, count(*) as file_count
    from {{ ref('dim_file') }}
    where is_trashed = 0
    group by tenant_id
)

select
    {{ business_date() }} as business_date,
    tenants.tenant_id,
    tenants.tenant_name,
    tenants.plan_tier,
    tenants.region_code,
    coalesce(usage.api_units, 0) as api_units,
    coalesce(usage.compute_units, 0) as compute_units,
    coalesce(storage.peak_storage_mb, 0) as storage_peak_mb,
    coalesce(storage.bytes_used, 0) as bytes_used,
    coalesce(active_users.active_users, 0) as active_users,
    coalesce(documents.document_count, 0) as document_count,
    coalesce(files.file_count, 0) as file_count
from {{ ref('dim_tenant') }} as tenants
left join usage on usage.tenant_id = tenants.tenant_id
left join {{ ref('rollup_storage_daily') }} as storage on storage.tenant_id = tenants.tenant_id
left join active_users on active_users.tenant_id = tenants.tenant_id
left join documents on documents.tenant_id = tenants.tenant_id
left join files on files.tenant_id = tenants.tenant_id
