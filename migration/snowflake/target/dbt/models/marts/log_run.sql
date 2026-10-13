{{ config(schema="OPS", materialized="table") }}

with rows_written as (
    select 'usp_load_dim_date' as object_name, count(*) as rows_written
    from {{ ref("dim_date") }}
    union all
    select 'usp_load_dim_tenant', count(*) from {{ ref("dim_tenant") }}
    union all
    select 'usp_load_dim_plan', count(*) from {{ ref("dim_plan") }}
    union all
    select 'usp_load_dim_user', count(*) from {{ ref("dim_user") }}
    union all
    select 'usp_load_dim_workspace', count(*) from {{ ref("dim_workspace") }}
    union all
    select 'usp_load_dim_document', count(*) from {{ ref("dim_document") }}
    union all
    select 'usp_load_dim_file', count(*) from {{ ref("dim_file") }}
    union all
    select 'usp_rollup_storage_daily', count(*)
    from {{ ref("rollup_storage_daily") }}
    where business_date = {{ business_date() }}
    union all
    select 'usp_rollup_usage_events', count(*)
    from {{ ref("rollup_usage_events") }}
    where business_date = {{ business_date() }}
    union all
    select 'usp_rollup_seats', count(*)
    from {{ ref("rollup_seats") }}
    where business_date = {{ business_date() }}
    union all
    select 'usp_rollup_collab_daily', count(*)
    from {{ ref("rollup_collab_daily") }}
    where business_date = {{ business_date() }}
    union all
    select 'usp_rollup_audit', count(*)
    from {{ ref("rollup_audit") }}
    where business_date = {{ business_date() }}
    union all
    select 'usp_rollup_document_status', count(*)
    from {{ ref("rollup_document_status") }}
    where business_date = {{ business_date() }}
    union all
    select 'usp_rollup_retention', count(*)
    from {{ ref("rollup_retention") }}
    where business_date = {{ business_date() }}
    union all
    select 'usp_build_invoice_lines', count(*)
    from {{ ref("build_invoice_lines") }}
    where business_date = {{ business_date() }}
    union all
    select 'usp_rate_overage', count(*)
    from {{ ref("rollup_storage_daily") }} as storage
    inner join {{ ref("dim_plan") }} as plan
        on plan.plan_id = storage.plan_id
    where storage.business_date = {{ business_date() }}
    union all
    select 'usp_apply_plan_limits', count(*)
    from {{ ref("rollup_seats") }} as seats
    inner join {{ ref("dim_plan") }} as plan
        on plan.plan_id = seats.plan_id
    where seats.business_date = {{ business_date() }}
    union all
    select 'usp_build_capacity_forecast_input', count(*)
    from {{ ref("build_capacity_forecast_input") }}
    where business_date = {{ business_date() }}
    union all
    select 'usp_build_mart_tenant_usage', count(*)
    from {{ ref("build_mart_tenant_usage") }}
    where business_date = {{ business_date() }}
    union all
    select 'usp_build_mart_plan_seat_summary', count(*)
    from {{ ref("build_mart_plan_seat_summary") }}
    where business_date = {{ business_date() }}
    union all
    select 'usp_build_mart_overage', count(*)
    from {{ ref("build_mart_overage") }}
    where business_date = {{ business_date() }}
    union all
    select 'usp_build_mart_retention', count(*)
    from {{ ref("build_mart_retention") }}
    where business_date = {{ business_date() }}
    union all
    select 'usp_build_mart_audit', count(*)
    from {{ ref("build_mart_audit") }}
    where business_date = {{ business_date() }}
)

select
    {{ business_date() }} as business_date,
    object_name,
    'procedure' as object_type,
    'succeeded' as status,
    rows_written
from rows_written
