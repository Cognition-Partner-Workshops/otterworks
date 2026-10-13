# The Usage & Billing Warehouse: estate specification

This file is the contract between the pieces of the Snowflake migration fixture. The source generator, the SQL Server schema, the SSIS packages, the report catalog, the dbt project and the parity gate all follow the names below. Change a name here first.

## Where it lives

```
migration/snowflake/
  ESTATE.md              this file
  README.md              how to run the fixture, what is real and what is replayed
  Makefile               sfm-* targets (also reachable from the repo root Makefile)
  compose.yaml           SQL Server 2022 (mcr.microsoft.com/mssql/server:2022-latest)
  source/
    generate.py          deterministic generator: reads the OtterWorks seed shapes, writes CSV extracts under source/build/
    ddl/                 one file per schema: stg.sql dim.sql fact.sql mart.sql ops.sql
    procs/               one file per procedure, usp_<name>.sql
    ssis/                twelve .dtsx packages (real SSIS package XML)
    reports/             thirty SSRS-style .rdl files, rpt_<name>.rdl
    agent/jobs.yaml      SQL Agent job catalog (jobs, steps, schedules), loaded into ops.agent_jobs
    agent/crontab.legacy the cron side of the schedule (the etl/ scripts that touch the warehouse)
    replay/ssis_replay.py   parses a .dtsx, runs its data flow against SQL Server, writes ops.etl_run_log
    replay/agent_replay.py  runs an agent job's steps in order against SQL Server
    load.py              creates the database, applies ddl/ and procs/, loads the generated extracts
  consumers/
    consumers.yaml       what report-service, admin-dashboard, analytics-service and the forecasting job read
  target/
    bootstrap/           Snowflake objects by run token: account.sql, teardown.sql, verify_clean.sql, bootstrap.py
    dbt/                 the dbt project (profiles read env, key-pair auth)
    tasks/               Snowflake task definitions that replace SQL Agent and cron
    python/              capacity_forecast.py ported to Snowpark
  gate/
    manifest.yaml        the 25 units, their source procedure, target model and compare keys
    parity.py            SQL Server vs Snowflake comparison, writes gate/out/ledger.json and ledger.md
    dual_run.py          runs both sides for a business date and calls parity.py
```

## SQL Server side

Database `OtterWorksUBW`. Login `sa` from compose; the harness uses `UBW_SQL_HOST`, `UBW_SQL_PORT`, `UBW_SQL_USER`, `UBW_SQL_PASSWORD`.

### Schemas and tables (40)

`stg` (14): landing tables filled by the SSIS packages.

| Table | Fed by package | Source service |
|---|---|---|
| stg_billing_tenants | pkg_billing_core | legacy-billing tenants |
| stg_billing_plans | pkg_billing_core | legacy-billing plans (starter, growth, scale) |
| stg_billing_subscriptions | pkg_billing_core | legacy-billing subscriptions |
| stg_billing_usage_events | pkg_billing_usage | legacy-billing usage_events (api, storage, compute) |
| stg_billing_invoices | pkg_billing_invoices | legacy-billing invoices and invoice lines |
| stg_auth_users | pkg_auth_users | auth-service users |
| stg_auth_workspace_members | pkg_auth_memberships | auth-service user roles per workspace |
| stg_documents | pkg_documents | document-service documents |
| stg_document_versions | pkg_document_versions | document-service document_versions |
| stg_files | pkg_files | file-service files and folders |
| stg_file_versions | pkg_file_versions | file-service file_versions |
| stg_collab_events | pkg_collaboration | document comments and collaboration sessions |
| stg_audit_events | pkg_audit | audit-service events |
| stg_analytics_events | pkg_analytics | analytics-service analytics_events |

`dim` (8): dim_date, dim_tenant, dim_plan, dim_user, dim_workspace, dim_document, dim_file, dim_region.

`fact` (8): fact_storage_usage_daily, fact_usage_events, fact_seat_assignments, fact_collab_activity_daily, fact_audit_events, fact_invoice_lines, fact_retention_actions, fact_document_status_daily.

`mart` (6): mart_tenant_usage_daily, mart_plan_seat_summary, mart_overage_charges, mart_retention_summary, mart_audit_rollup, mart_capacity_forecast_input.

`ops` (4): etl_run_log, agent_jobs, agent_job_history, parity_watermarks.

Every stg table carries `extracted_at datetime2` and `source_system nvarchar(40)`. Every fact and mart table carries `business_date date` and `loaded_at datetime2`. Timestamps from the services arrive as UTC `datetime2`; the SQL Server instance runs with its server clock in `US Eastern` by convention of the legacy team, and procedures use `GETDATE()` and `CAST(... AS date)` the way the legacy team wrote them.

### Procedures (25)

Dimension loads (7): usp_load_dim_date, usp_load_dim_tenant, usp_load_dim_plan, usp_load_dim_user, usp_load_dim_workspace, usp_load_dim_document, usp_load_dim_file.

Rollups (8): usp_rollup_storage_daily, usp_rollup_usage_events, usp_rollup_seats, usp_rollup_collab_daily, usp_rollup_audit, usp_rollup_document_status, usp_rollup_retention, usp_build_invoice_lines.

Rating (3): usp_rate_overage, usp_apply_plan_limits, usp_build_capacity_forecast_input.

Marts (5): usp_build_mart_tenant_usage, usp_build_mart_plan_seat_summary, usp_build_mart_overage, usp_build_mart_retention, usp_build_mart_audit.

Operations (2): usp_log_run, usp_purge_expired.

Each procedure takes `@business_date date` (operations procedures take what they need) and is idempotent for that date. Procedures are written the way a 2016-era team wrote them: cursors where a set would do, `GETDATE()` for timestamps, integer arithmetic for money, string literals for plan tiers.

### SSIS packages (12)

pkg_billing_core, pkg_billing_usage, pkg_billing_invoices, pkg_auth_users, pkg_auth_memberships, pkg_documents, pkg_document_versions, pkg_files, pkg_file_versions, pkg_collaboration, pkg_audit, pkg_analytics.

Each `.dtsx` is real SSIS package XML: a connection manager per source, a Data Flow task with an OLE DB or flat-file source, at least one Derived Column or Lookup transform, and an OLE DB destination into the matching `stg` table. Three packages (pkg_billing_usage, pkg_files, pkg_analytics) also carry a Script Task whose C# body does something the data flow cannot (a watermark read, a unit conversion, a checksum). The replay harness interprets the data flow and the Script Task's documented intent; it does not execute C#.

### Reports (30)

Thirty `.rdl` files under `source/reports/`, each with a DataSet query against `mart` or `fact` tables, parameters, and a Tablix. Families: tenant usage (8), plan and seats (6), overage and billing (6), retention and compliance (5), audit (3), capacity (2). Names start `rpt_` and match the file name. `rpt_plan_tier_summary` is the plan-tier report with a tier filter parameter.

### Scheduling

`source/agent/jobs.yaml` holds four SQL Agent jobs: `UBW Nightly Load` (packages then procedures in order), `UBW Hourly Audit`, `UBW Weekly Retention`, `UBW Monthly Overage`. `source/agent/crontab.legacy` lists the cron entries that touch the warehouse, including the weekly `etl/scripts/capacity_forecast_weekly.py` job that reads `mart_capacity_forecast_input` and writes `mart_capacity_forecast_input` back with a forecast column.

## Consumers

`consumers/consumers.yaml` names four readers, the tables or reports each one reads and the query shape:

- report-service: the thirty report definitions, through a JDBC read of the `mart` schema.
- admin-dashboard usage pages: `mart_tenant_usage_daily`, `mart_plan_seat_summary`.
- analytics-service: `fact_usage_events`, `mart_tenant_usage_daily` for the usage API.
- capacity forecasting job (`etl/` Python): `mart_capacity_forecast_input`.

The fixture adds the forecasting job as `etl/scripts/capacity_forecast_weekly.py` reading SQL Server through `pymssql`, selected by `UBW_BACKEND=sqlserver|snowflake`. The other three consumers are repointed by the migration sessions on the demo branch.

## Snowflake side

Objects carry the run token in their names and in the tag `OW_UBW.TAGS.RUN`, with `OW_UBW.TAGS.EXPIRES` as a second tag. Snowflake tags need a database and schema, so both live in a small shared `OW_UBW` database with a `TAGS` schema that teardown leaves in place. For token `sfm-20261012-bd` the names are:

| Object | Name |
|---|---|
| Database | `OW_UBW_SFM_20261012_BD` with schemas `RAW`, `STAGING`, `MARTS`, `OPS` |
| Warehouse | `OW_UBW_SFM_20261012_BD_WH` (X-Small, auto-suspend 60 seconds, auto-resume) |
| Roles | `OW_UBW_SFM_20261012_BD_ENGINEER` (create and run in the database), `OW_UBW_SFM_20261012_BD_READER` (select and monitor only) |
| Service user | `OW_UBW_SFM_20261012_BD_DBT` (key pair, default role ENGINEER) |
| Snowsight login | `OW_UBW_SFM_20261012_BD_VIEWER` (password, default role READER, for screen recordings) |
| Resource monitor | `OW_UBW_SFM_20261012_BD_RM` (credit quota set at bootstrap, suspend at 100 percent) |

`RAW` receives the stg extracts (the harness loads the same CSVs the SSIS replay loaded, through PUT and COPY INTO). `STAGING` and `MARTS` are dbt-owned. `OPS` holds `ETL_RUN_LOG`, `PARITY_LEDGER` and the task history view.

The dbt project maps one model per procedure, same names without the `usp_` prefix (`rollup_storage_daily`, `rate_overage`, ...), with `schema.yml` tests on keys and accepted values. Snowflake tasks under `target/tasks/` replace the four agent jobs and the cron entry, as a task graph rooted at `UBW_NIGHTLY_LOAD`.

## The gate

`gate/manifest.yaml` lists 25 units. Each unit names its source procedure, the mart or fact table it owns, the target dbt model, the compare keys and the compare columns. `gate/parity.py` runs for a business date, pulls both sides with the same keys and columns, and writes a ledger with one row per unit:

- `PASS`: every row matches on every compared column.
- `DIVERGE`: rows differ; the ledger records the first ten differing keys and the column, and a free-text `explanation` field that a session fills in by editing `gate/out/ledger.md`.
- `PENDING`: the target model does not exist yet.

`make sfm-gate RUN=<token> DATE=<yyyy-mm-dd>` prints `Parity PASS=<n> DIVERGE=<n> PENDING=<n>` and exits non-zero while any unit is `PENDING` or any `DIVERGE` has no explanation. `make sfm-dual-run` runs the agent replay and the dbt build for the same date first, then the gate. `make sfm-cutover` stops the SQL Server replay, flips `UBW_BACKEND=snowflake` for the consumers, and re-runs the gate from the last dual-run ledger.

## Make targets

| Target | Does |
|---|---|
| `sfm-up` | compose up, generate extracts, create database, apply ddl and procs, replay the twelve packages, run the nightly job for the seed dates |
| `sfm-down` | compose down with volumes |
| `sfm-bootstrap RUN=` | create the Snowflake objects for the token (builder credentials) |
| `sfm-load-raw RUN=` | load the extracts into `RAW` |
| `sfm-dbt RUN=` | dbt build against the token's database |
| `sfm-gate RUN= DATE=` | parity, prints the summary line |
| `sfm-dual-run RUN= DATE=` | both sides then the gate |
| `sfm-cutover RUN=` | decommission SQL Server and prove the consumers read Snowflake |
| `sfm-teardown RUN=` | drop every Snowflake object with the token |
| `sfm-verify-clean RUN=` | list anything that still carries the token; non-zero if anything answers |

## Seed shape and dates

The generator is seeded with `UBW_SEED=20261012` and produces 60 tenants across the three plans, about 2,400 users, 180 workspaces (some users in two workspaces), 40,000 documents, 25,000 files, usage events and audit events for the 31 days of 2026-09-01 through 2026-10-01, and invoices for August and September. Business dates for the fixture runs are 2026-09-15 (the parity date) and 2026-09-30 (the month-end date). Timestamps are generated in UTC with a deliberate spread across the day, including the hours around midnight UTC.
