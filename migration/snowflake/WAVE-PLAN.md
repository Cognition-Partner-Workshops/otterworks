# Usage & Billing Warehouse — wave plan

Twenty-five procedures, ordered so the number finance argues about moves first and every
wave lands on tables the earlier waves already proved. The units come from
`gate/manifest.yaml`; each is handed out with
[`.workshop/playbooks/snowflake-migration-unit.devin.md`](../../.workshop/playbooks/snowflake-migration-unit.devin.md).
Inventory: [`INVENTORY.md`](INVENTORY.md).

Each wave is done when `make sfm-gate RUN=$UBW_RUN DATE=2026-09-15` and `DATE=2026-09-30` show
its units as `PASS` or an explained `DIVERGE`, its reports read the Snowflake tables, and the
agent/cron steps it replaces are Snowflake tasks.

| Wave | Units (procedure → dbt model) | Packages → staging | Reports / consumers | Schedules replaced | Known difference to expect |
|---|---|---|---|---|---|
| 0 (done before this PR) | 7 `usp_load_dim_*` → `dim_*` | pkg_billing_core, pkg_auth_*, pkg_documents, pkg_files (sources) | — | Nightly dim steps | — |
| **1 Storage usage (this PR)** | **usp_rollup_storage_daily → rollup_storage_daily**; usp_build_mart_tenant_usage → build_mart_tenant_usage, with its inputs usp_rollup_usage_events → rollup_usage_events and usp_rollup_audit → rollup_audit | pkg_billing_usage → stg_billing_usage_events; pkg_audit → stg_audit_events | 8 `rpt_tenant_*` (views follow in wave 6); admin-dashboard and analytics-service usage pages | Nightly step 21 → task `UBW_ROLLUP_STORAGE_DAILY` | UTC date boundary in the storage rollup (legacy defect) |
| 2 Overage and invoices | usp_rate_overage, usp_build_mart_overage, usp_build_invoice_lines | pkg_billing_invoices | rpt_overage_charges, rpt_overage_by_tier, rpt_storage_vs_included, 3 invoice reports | Monthly Overage job; cron `export_overage.sh` | integer division in per-GB overage proration (legacy defect) |
| 3 Seats and plans | usp_rollup_seats, usp_apply_plan_limits, usp_build_mart_plan_seat_summary | pkg_auth_memberships, pkg_auth_users | 4 seat reports, rpt_plan_mix, rpt_plan_tier_summary; admin-dashboard | Nightly seat steps | seats counted twice across workspaces (source bug, data owners decide); case-sensitive plan-tier filter (legacy defect) |
| 4 Content lifecycle | usp_rollup_document_status, usp_rollup_retention, usp_build_mart_retention, usp_purge_expired, usp_rollup_collab_daily | pkg_document_versions, pkg_file_versions, pkg_collaboration | rpt_document_status, 4 retention/trash reports | Weekly Retention job | NULL archived flag counted as active (legacy defect) |
| 5 Audit | usp_build_mart_audit (rollup_audit moved in wave 1) | — | rpt_audit_rollup, rpt_audit_sensitive_actions, rpt_audit_user_activity | Hourly Audit job | — |
| 6 Forecast, analytics, reports | usp_build_capacity_forecast_input, usp_log_run | pkg_analytics (Script Task → Snowpark) | rpt_capacity_forecast, rpt_storage_growth_trend; one view per report in `REPORTS`; capacity-forecasting-job (`UBW_BACKEND=snowflake`), report-service JDBC repoint | cron `capacity_forecast_weekly.py`, `analytics_daily.py`, `check_stuck_runs.sh` | — |
| 7 Dual run and cutover | — | — | all four consumers on Snowflake | SQL Agent disabled | `make sfm-dual-run` nightly until clean, then `make sfm-cutover` |

## Why storage goes first

- It is the only fact that reaches finance twice: the usage pages (via `mart_tenant_usage_daily`)
  and overage invoices (via `usp_rate_overage` → `mart_overage_charges` → `export_overage.sh`).
- It needs nothing but `stg_billing_usage_events`, `dim_tenant` and `dim_plan`, which wave 0
  already has in Snowflake, so a difference in the gate is the procedure's logic and nothing else.
- Wave 2 (overage) prices from this fact; proving it first means overage parity is about the
  proration arithmetic only.
