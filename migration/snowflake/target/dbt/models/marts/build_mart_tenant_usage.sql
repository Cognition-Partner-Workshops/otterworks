{{ config(
    materialized="incremental",
    incremental_strategy="delete+insert",
    unique_key="business_date"
) }}

with usage_by_tenant as (
    select
        tenant_id,
        sum(case when event_kind = 'api' then units else 0 end) as api_units,
        sum(case when event_kind = 'compute' then units else 0 end) as compute_units
    from {{ ref("rollup_usage_events") }}
    where business_date = {{ business_date() }}
    group by tenant_id
),
storage_by_tenant as (
    select tenant_id, peak_storage_mb, bytes_used
    from {{ ref("rollup_storage_daily") }}
    where business_date = {{ business_date() }}
),
users_by_tenant as (
    select tenant_id, count(distinct user_id) as active_users
    from {{ ref("rollup_audit") }}
    where business_date = {{ business_date() }}
    group by tenant_id
),
documents_by_tenant as (
    select tenant_id, count(*) as document_count
    from {{ ref("dim_document") }}
    where is_deleted = 0
    group by tenant_id
),
files_by_tenant as (
    select tenant_id, count(*) as file_count
    from {{ ref("dim_file") }}
    where is_trashed = 0
    group by tenant_id
)

select
    {{ business_date() }} as business_date,
    t.tenant_id,
    t.tenant_name,
    t.plan_tier,
    t.region_code,
    coalesce(u.api_units, 0) as api_units,
    coalesce(u.compute_units, 0) as compute_units,
    coalesce(s.peak_storage_mb, 0) as storage_peak_mb,
    coalesce(s.bytes_used, 0) as bytes_used,
    coalesce(a.active_users, 0) as active_users,
    coalesce(d.document_count, 0) as document_count,
    coalesce(f.file_count, 0) as file_count
from {{ ref("dim_tenant") }} as t
left join usage_by_tenant as u
    on u.tenant_id = t.tenant_id
left join storage_by_tenant as s
    on s.tenant_id = t.tenant_id
left join users_by_tenant as a
    on a.tenant_id = t.tenant_id
left join documents_by_tenant as d
    on d.tenant_id = t.tenant_id
left join files_by_tenant as f
    on f.tenant_id = t.tenant_id
