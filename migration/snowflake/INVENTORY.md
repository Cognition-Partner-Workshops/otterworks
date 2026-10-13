# Usage & Billing Warehouse — inventory

What the SQL Server warehouse on `demo-snowflake-migration` is made of, read from
`migration/snowflake/source/` (package XML, procedures, report definitions, `agent/jobs.yaml`,
`agent/crontab.legacy`) and `consumers/consumers.yaml`. The wave plan is in
[`WAVE-PLAN.md`](WAVE-PLAN.md).

## The storage number in one paragraph

Storage samples arrive from the billing service through `pkg_billing_usage` into
`stg.stg_billing_usage_events` (kind `storage`, one sample per tenant per hour, MB, UTC
timestamps). Every night at 02:30 step 21 of **UBW Nightly Load** runs
`usp_rollup_storage_daily`, which keeps each tenant's daily peak in
`fact.fact_storage_usage_daily`. Two things read that fact: step 31
`usp_build_mart_tenant_usage` copies the peak into `mart.mart_tenant_usage_daily` (the usage
pages, eight `rpt_tenant_*` reports, admin-dashboard, analytics-service), and on the 1st of the
month **UBW Monthly Overage** runs `usp_rate_overage` (writes `overage_gb` / `overage_cents`
back onto the same fact) and `usp_build_mart_overage`, which `export_overage.sh` and three
overage reports read. So the daily storage peak is what finance sees on the usage pages **and**
what overage invoices are priced from.

## Feeds: source service → SSIS package → staging table

| Package | Source service | Writes | Script Task (C#) |
|---|---|---|---|
| pkg_billing_core | billing | stg_billing_plans, stg_billing_subscriptions, stg_billing_tenants | yes |
| pkg_billing_usage | billing | stg_billing_usage_events | yes (reads usage watermark) |
| pkg_billing_invoices | billing | stg_billing_invoices | yes |
| pkg_auth_users | auth | stg_auth_users | |
| pkg_auth_memberships | auth | stg_auth_workspace_members | |
| pkg_documents | document | stg_documents | |
| pkg_document_versions | document | stg_document_versions | |
| pkg_files | file | stg_files | yes |
| pkg_file_versions | file | stg_file_versions | |
| pkg_collaboration | collaboration | stg_collab_events | |
| pkg_audit | audit | stg_audit_events | |
| pkg_analytics | analytics | stg_analytics_events | yes |

The replay harness used for parity reads the package XML and lands the same extracts; it does
not execute SSIS or the C# Script Tasks.

## Procedures: what each reads and owns

| Procedure | Reads | Owns (writes) | Scheduled by |
|---|---|---|---|
| usp_load_dim_date | — | dim.dim_date | Nightly step 13 |
| usp_load_dim_plan | stg_billing_plans | dim.dim_plan | Nightly |
| usp_load_dim_tenant | stg_billing_tenants, stg_billing_subscriptions, dim_plan | dim.dim_tenant | Nightly |
| usp_load_dim_user | stg_auth_users, stg_auth_workspace_members | dim.dim_user | Nightly |
| usp_load_dim_workspace | stg_auth_workspace_members | dim.dim_workspace | Nightly |
| usp_load_dim_document | stg_documents, stg_document_versions | dim.dim_document | Nightly |
| usp_load_dim_file | stg_files, stg_file_versions | dim.dim_file | Nightly |
| usp_rollup_usage_events | stg_billing_usage_events | fact.fact_usage_events | Nightly step 20 |
| **usp_rollup_storage_daily** | stg_billing_usage_events, dim_tenant, dim_plan | **fact.fact_storage_usage_daily** | **Nightly step 21** |
| usp_rollup_seats | stg_auth_workspace_members, dim_user, dim_tenant | fact.fact_seat_assignments | Nightly |
| usp_rollup_collab_daily | stg_collab_events | fact.fact_collab_activity_daily | Nightly |
| usp_rollup_audit | stg_audit_events | fact.fact_audit_events | Nightly + Hourly Audit |
| usp_rollup_document_status | dim_document | fact.fact_document_status_daily | Nightly |
| usp_rollup_retention | dim_document, dim_file | fact.fact_retention_actions | Nightly + Weekly Retention |
| usp_build_invoice_lines | stg_billing_invoices | fact.fact_invoice_lines | Nightly + Monthly Overage |
| usp_rate_overage | fact_storage_usage_daily, dim_plan | fact.fact_storage_usage_daily (overage columns) | Monthly Overage |
| usp_apply_plan_limits | fact_seat_assignments, dim_plan | — (flags only) | Nightly |
| usp_build_capacity_forecast_input | stg_billing_usage_events, fact_seat_assignments, dim_tenant | mart.mart_capacity_forecast_input | Nightly |
| **usp_build_mart_tenant_usage** | dim_tenant, fact_usage_events, **fact_storage_usage_daily**, fact_audit_events, dim_document, dim_file | **mart.mart_tenant_usage_daily** | Nightly step 31 |
| usp_build_mart_plan_seat_summary | fact_seat_assignments | mart.mart_plan_seat_summary | Nightly |
| usp_build_mart_overage | fact_storage_usage_daily, dim_tenant, dim_plan | mart.mart_overage_charges | Monthly Overage |
| usp_build_mart_retention | fact_retention_actions | mart.mart_retention_summary | Weekly Retention |
| usp_build_mart_audit | fact_audit_events | mart.mart_audit_rollup | Hourly Audit |
| usp_log_run | — | ops.etl_run_log | every step |
| usp_purge_expired | ops.etl_run_log, ops.agent_job_history | deletes from fact_usage_events, fact_audit_events | Weekly Retention |

## Reports: which table each reads

| Table | Reports |
|---|---|
| **mart.mart_tenant_usage_daily** | rpt_tenant_usage_daily, **rpt_tenant_storage_peak**, rpt_tenant_usage_top20, rpt_tenant_usage_by_region, rpt_tenant_api_units, rpt_tenant_compute_units, rpt_tenant_active_users, rpt_tenant_content_counts |
| mart.mart_overage_charges (priced from fact_storage_usage_daily) | rpt_overage_charges, rpt_overage_by_tier, **rpt_storage_vs_included** |
| fact.fact_invoice_lines | rpt_invoice_lines, rpt_invoice_totals_by_tenant, rpt_monthly_billing_summary |
| fact.fact_seat_assignments | rpt_seat_count_by_tenant, rpt_seat_utilization, rpt_seat_limit_headroom, rpt_seats_over_limit |
| mart.mart_plan_seat_summary | rpt_plan_mix, rpt_plan_tier_summary |
| mart.mart_capacity_forecast_input | rpt_capacity_forecast, rpt_storage_growth_trend |
| mart.mart_retention_summary | rpt_retention_summary, rpt_archived_content |
| fact.fact_retention_actions | rpt_retention_candidates, rpt_trash_purge_candidates |
| fact.fact_document_status_daily | rpt_document_status |
| mart.mart_audit_rollup | rpt_audit_rollup |
| fact.fact_audit_events | rpt_audit_sensitive_actions, rpt_audit_user_activity |

## Consumers

| Consumer | Reads | How |
|---|---|---|
| report-service | all 30 report definitions (mart and fact schemas) | JDBC |
| admin-dashboard | mart_tenant_usage_daily, mart_plan_seat_summary | direct SQL |
| analytics-service | fact_usage_events, mart_tenant_usage_daily | direct SQL |
| capacity-forecasting-job | reads/writes mart_capacity_forecast_input (`etl/scripts/capacity_forecast_weekly.py`) | `UBW_BACKEND` switch |

## Schedules

| Scheduler | Job / entry | When (US Eastern) | Runs |
|---|---|---|---|
| SQL Agent | UBW Nightly Load | daily 02:30 | 12 packages, 7 dims, rollups, plan limits, capacity input, 4 marts (35 steps) |
| SQL Agent | UBW Hourly Audit | hourly at :05 | usp_rollup_audit, usp_build_mart_audit |
| SQL Agent | UBW Weekly Retention | Sunday 03:00 | usp_rollup_retention, usp_build_mart_retention, usp_purge_expired |
| SQL Agent | UBW Monthly Overage | 1st at 04:00 | usp_rate_overage, usp_build_mart_overage, usp_build_invoice_lines |
| cron | analytics_daily.py | daily 05:00 | analytics export |
| cron | capacity_forecast_weekly.py | Monday 06:15 | capacity-forecasting-job |
| cron | export_overage.sh | 1st at 01:10 | overage export to billing |
| cron | check_stuck_runs.sh | every 10 min | ETL run watchdog |
