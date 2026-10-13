-- dbo.usp_log_run: ops.etl_run_log, one row per package and procedure the nightly load ran for
-- the business date, with the rows it wrote.
--
-- In SQL Server every package and procedure calls usp_log_run itself. In Snowflake the task graph
-- (target/tasks/) records its own steps in OPS.ETL_RUN_LOG; this model is the business view of
-- the same thing in the legacy shape: rows_written is the row count each replacement model holds
-- for the business date, counted after dbt has built it (the refs below order this model last).
-- pkg_billing_usage only appends events past its watermark, so it reports the rows the current
-- dbt invocation appended (0 on a re-run), as the legacy package does.
{{ config(materialized='incremental', incremental_strategy='delete+insert', unique_key='business_date') }}

{%- set bd = business_date() %}
{%- set packages = [
    ('pkg_billing_core', ['stg_billing_tenants', 'stg_billing_plans', 'stg_billing_subscriptions']),
    ('pkg_billing_invoices', ['stg_billing_invoices']),
    ('pkg_auth_users', ['stg_auth_users']),
    ('pkg_auth_memberships', ['stg_auth_workspace_members']),
    ('pkg_documents', ['stg_documents']),
    ('pkg_document_versions', ['stg_document_versions']),
    ('pkg_files', ['stg_files']),
    ('pkg_file_versions', ['stg_file_versions']),
    ('pkg_collaboration', ['stg_collab_events']),
    ('pkg_audit', ['stg_audit_events']),
    ('pkg_analytics', ['stg_analytics_events']),
] %}
{%- set dims = ['dim_date', 'dim_plan', 'dim_tenant', 'dim_workspace', 'dim_user', 'dim_document', 'dim_file'] %}
{%- set facts = [
    ('rollup_usage_events', none),
    ('rollup_storage_daily', none),
    ('rollup_seats', none),
    ('rollup_collab_daily', none),
    ('rollup_audit', none),
    ('rollup_document_status', none),
    ('rollup_retention', none),
    ('build_invoice_lines', none),
    ('rate_overage', 'overage_gb is not null'),
    ('apply_plan_limits', 'seat_limit is not null'),
    ('build_capacity_forecast_input', none),
    ('build_mart_tenant_usage', none),
    ('build_mart_plan_seat_summary', none),
    ('build_mart_overage', none),
    ('build_mart_retention', none),
    ('build_mart_audit', none),
] %}

with steps as (
    {% for package, models in packages -%}
    select '{{ package }}' as object_name, 'package' as object_type, (
        {%- for model in models %}
        (select count(*) from {{ ref(model) }}){% if not loop.last %} +{% endif %}
        {%- endfor %}
    ) as rows_written
    union all
    {% endfor -%}
    select 'pkg_billing_usage', 'package', (
        select count(*) from {{ ref('stg_billing_usage_events') }}
        where extracted_at >= convert_timezone(
            'America/New_York', '{{ run_started_at.strftime("%Y-%m-%d %H:%M:%S") }} +0000'::timestamp_tz
        )::timestamp_ntz
    )
    {% for model in dims -%}
    union all
    select 'usp_load_{{ model }}', 'procedure', (select count(*) from {{ ref(model) }})
    {% endfor -%}
    {% for model, condition in facts -%}
    union all
    select 'usp_{{ model }}', 'procedure', (
        select count(*) from {{ ref(model) }}
        where business_date = {{ bd }}{% if condition %} and {{ condition }}{% endif %}
    )
    {% endfor %}
)

select
    {{ bd }} as business_date,
    object_name,
    object_type,
    'succeeded' as status,
    rows_written,
    current_timestamp()::timestamp_ntz as logged_at
from steps
