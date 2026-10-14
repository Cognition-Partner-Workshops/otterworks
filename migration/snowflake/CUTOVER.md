# Usage & Billing Warehouse cutover record: SQL Server to Snowflake

Run `sfm-20261013-lv` (database `OW_UBW_SFM_20261013_LV`). The cutover was cut from PR #1978
(`devin/1791861351-sfm-report-layer`), which stacks waves one to three on `demo-snowflake-migration`.
`make sfm-cutover RUN=$UBW_RUN` was run once, on 2026-10-13 at 04:37 UTC, with all four legacy flags off.

## Decision

Finance and Billing decided that the corrected numbers go live at cutover for all four flagged
behaviours, seats included. The configuration that ships is the gated one, with every legacy flag
off:

| dbt var | Shipped value |
|---|---|
| `legacy_storage_day_eastern_fixed_offset` | `false` |
| `legacy_overage_whole_gb_truncation` | `false` |
| `legacy_null_archived_counted_active` | `false` |
| `legacy_seats_count_workspace_memberships` | `false`. Billing can still get the legacy count by setting it to `true`. |

Ledger rows that still said the decision was open (`gate/out/ledger.md`, `gate/out/2026-09-15/ledger.md`,
`gate/out/reports.md`, `gate/out/2026-09-15/reports.md`) now record the decision. No gated number and
no `ledger.json` changed. `parity.py --reread` still prints `Parity PASS=15 DIVERGE=10 PENDING=0`.

## Seats: both numbers

| Business date | Legacy (`legacy_seats_count_workspace_memberships=true`) | Shipped (distinct users per tenant) |
|---|---:|---:|
| 2026-09-15 | 2,608 | 2,363 |
| 2026-09-30 | 2,649 | 2,399 |

**Why they differ: a bug in the auth source.** `pkg_auth_memberships` lands 2,650 workspace-membership rows
for 2,400 users, because 250 users belong to two workspaces of the same tenant. `dbo.usp_rollup_seats`
joins users to every membership row and runs `COUNT(*)`, so each of those users is counted twice.
Snowflake counts each user once per tenant. Tenants over their seat limit stay at 30 either way.

**First follow-up (out of scope for this pass):** add a side-by-side seat column to the admin-dashboard
`/usage` page showing the shipped and legacy counts.

## Review of the representative PR

PR #1978 at `eebb2f9ab` has no review comments or reviews, and its 7 CI checks pass. The review of its
evidence is the unit table below. Two ledger explanations did not add up; both were checked against
Snowflake and corrected in `ledger.md` without rerunning a unit.

## Unit state (both parity dates: 2026-09-15 and 2026-09-30)

On each date: `PASS=15 DIVERGE=10 PENDING=0`, gate exit 0. The same ten units diverge on both dates.

| Unit | State | Does the explanation hold up against the ledger and gate output? |
|---|---|---|
| load_dim_date | PASS | — |
| load_dim_tenant | PASS | — |
| load_dim_plan | PASS | — (inherits the plan `active` defect, see below) |
| load_dim_user | PASS | — |
| load_dim_workspace | PASS | — |
| load_dim_document | PASS | — |
| load_dim_file | PASS | — |
| rollup_storage_daily | DIVERGE | Yes. The source proc's `DATEADD(hour,-4,…)` produces the per-tenant peak differences in the ledger samples, and with the legacy flag on it gives PASS on both dates. |
| rollup_usage_events | PASS | — |
| rollup_seats | DIVERGE | Yes. 2,650 membership rows vs 2,400 users matches 2,608/2,649 vs 2,363/2,399, and the flag gives PASS. |
| rollup_collab_daily | PASS | — |
| rollup_audit | PASS | — |
| rollup_document_status | DIVERGE | Yes. NULL `archived` moves from `active` to `unknown` (`active` 33,910→32,758 on 2026-09-15 and 34,066→32,914 on 2026-09-30), and the flag gives PASS. |
| rollup_retention | PASS | — |
| build_invoice_lines | PASS | — |
| rate_overage | DIVERGE | Yes. Bigint whole-GB truncation plus the storage-day shift explain 31,423→29,787 and 76,616→75,243 cents. Both flags give PASS. |
| apply_plan_limits | PASS | — |
| build_capacity_forecast_input | DIVERGE | Holds after a correction. The cause (storage-day bucketing and seats) is right, but the 2026-09-15 row-count reason was wrong: it said the window "reaches into 2026-08-18 Eastern". The real reason: the legacy Eastern day 2026-08-31 takes the 2026-09-01 00:00–03:59 UTC samples of all 60 tenants (16×60 = 960), while the UTC day 2026-08-31 holds only the 26 tenants whose first sample was jittered before midnight (15×60+26 = 926). A read of `MARTS.BUILD_CAPACITY_FORECAST_INPUT` confirmed 26 rows for 2026-08-31. The ledger text is corrected; no rerun was needed. |
| build_mart_tenant_usage | DIVERGE | Yes. Only `storage_peak_mb` and `bytes_used` differ, and both are copied from the storage fact. The flag gives PASS. |
| build_mart_plan_seat_summary | DIVERGE | Yes. `seat_count` and the average differ; tenant count, limits and over-limit match. The flag gives PASS. |
| build_mart_overage | DIVERGE | Yes. The differences are inherited from rate_overage and the storage day; tenant, tier, included bytes and rate match. |
| build_mart_retention | PASS | — |
| build_mart_audit | PASS | — |
| log_run | DIVERGE | Holds after a completion. On 2026-09-30 the 47 vs 35 rows come from 12 package keys that are logged twice on SQL Server (the initial replay plus the nightly run). The 13th differing key, which the text did not account for, is `usp_rollup_document_status` (rows_written 360 vs 540; `OPS.LOG_RUN` shows 540). On 2026-09-15 the 2 keys are the row counts of the two models that diverge by design. The text is completed; no rerun was needed. |
| purge_expired | DIVERGE | Yes. This is an operational shape difference: legacy keeps history rows per object, Snowflake keeps the latest status. All 35 objects are present and `succeeded`. |

Reports: `PASS=14 DIVERGE=16` on both dates. Every divergence is inherited from one of the four flagged
behaviours. With the legacy flags on (`gate/out/legacy-flags/`), 30 of 30 reports pass on 2026-09-30 and 29 of 30 on 2026-09-15.
The one that still differs is `rpt_seat_utilization`: 5 tenants differ in the 15th decimal (SQL Server truncates, Snowflake rounds).
With the flags on, the only units that still diverge are `purge_expired` (both dates) and `log_run` (2026-09-30), which are operational shape differences.

## Legacy behaviour that is wrong by design: corrected at cutover

| Behaviour | Business reason it was wrong | What the data owners inherit |
|---|---|---|
| Storage day uses a fixed −4h offset (`DATEADD(hour,-4,utc)`) | Each business day took 00:00–03:59 UTC of the next day, and it is an hour off whenever Eastern is on standard time. | Peak storage drops 0.44% (2026-09-15) and 0.30% (2026-09-30); for example, tenant 06164f4b on 2026-09-30 goes from 636,141 MB (a 2026-10-01 01:05 UTC sample) to 629,150 MB. Usage pages and overage pricing move with it. |
| Overage drops partial GBs (bigint division) | Customers were invoiced on the truncated GB count. | Overage goes from 31,423 to 29,787 cents and from 76,616 to 75,243 cents (this also includes the storage-day shift). Invoices now come from the byte-prorated number. |
| NULL `archived` counted as active | A missing archive flag was reported as active. | 1,152 documents move to `unknown`. Nothing is invoiced from this. |
| Seats count membership rows | Users in two workspaces of one tenant were counted twice. | See "Seats: both numbers". The legacy count stays available to Billing behind its flag. |

## Legacy behaviour that is wrong by design: still reproduced (staging, not changed in this pass)

The SSIS ports (`gate/out/staging/*.md`) reproduce `stg.*` row for row, including these defects:

- **All 7 plans land inactive** (`pkg_billing_core`). The package compares `LOWER(active) == "true"` but the source carries `t`/`f`. Anything filtering on `dim_plan.is_active` sees no active plans.
- **Usage watermark never revisits** (`pkg_billing_usage`). Late or corrected usage events with a timestamp below the watermark are never loaded, so they are never billed. The watermark is not capped at the business date either, so future-dated events load early and a backfill loads nothing.
- **Invoice `line_id` is blank** (`pkg_billing_invoices`): the destination maps `line_id`, but the flat file calls the column `id` and nothing renames it, so all 376 lines land blank.
- **`tax_exempt` uses a case-sensitive `== "t"`** (`pkg_billing_core`), so any other spelling is charged tax.
- **Multi-tenant users are attributed to `MIN(tenant_id)`** in analytics and audit, and an unmatched lookup lands NULL tenant.
- **Timestamps:** analytics truncates to the second (`DT_I4`, which also overflows in 2038), audit to microseconds, and several packages strip the timezone as text.
- **Versions after the business date** count towards `version_count`. `size_mb` is MiB, labelled MB, and rounded. The overage rate is rounded to whole cents per GB.

## Cutover verification

Full transcript: see the PR attachment (`cutover-transcript.txt`).

- `make sfm-cutover RUN=sfm-20261013-lv` exited 0 and wrote `migration/snowflake/.backend.env` = `UBW_BACKEND=snowflake`.
- **SQL Server is stopped.** `compose.yaml` defines `ubw-sql`, and cutover ran `docker compose stop ubw-sql`. No `ubw-sql` container existed on this host before or after the run (`docker compose ps -a` is empty). Port 1433 refuses connections. The dual-run replay container was already gone, so the stop had nothing to stop.
- **The gate still passes from the last ledger.** The cutover's reread of `gate/out/ledger.json` (2026-09-30) printed `Parity PASS=15 DIVERGE=10 PENDING=0`, exit 0.
- **Consumers on `UBW_BACKEND=snowflake`:** each consumer was started with `.backend.env` sourced (`UBW_BACKEND=snowflake`) and read business date 2026-09-30.
  - report-service (`:8091`): `GET /api/v1/reports/ubw/rpt_tenant_usage_daily` returned `backend=snowflake`, `REPORTS.RPT_TENANT_USAGE_DAILY`, 60 rows. `rpt_seat_count_by_tenant` returned `backend=snowflake`, 60 rows, `seat_count_total=2399` (the shipped seat number).
  - analytics-service (`:8088`): `/api/v1/analytics/ubw/usage` returned `backend=snowflake` from `MARTS.ROLLUP_USAGE_EVENTS` (180 rows). `/tenant-usage` returned `backend=snowflake` from `REPORTS.RPT_TENANT_USAGE_DAILY` (60 rows).
  - admin-dashboard (`:4200`, proxying to report-service): `/usage` returned HTTP 200, and its proxied report call returned `backend=snowflake` (60 rows).
  - capacity forecast job (`etl/scripts/capacity_forecast_weekly.py --business-date 2026-09-30`, which calls `OPS.UBW_CAPACITY_FORECAST_WEEKLY`): `Forecasted 60 tenants for 2026-09-30: 1680 observations, 30-day horizon`.
  - Unrelated backing stores were stubbed only to boot the services locally: report-service used the Spring `test` profile (H2 for its non-UBW JPA datasource), and analytics-service used `ANALYTICS_REPOSITORY_BACKEND=in-memory`. UBW reads went to Snowflake in every case.

## Snowsight (as the run's VIEWER user)

The run database has the `MARTS` schema with 23 objects. The task graph (root `OPS.UBW_NIGHTLY_LOAD`)
runs UBW_LOAD_RAW → UBW_BUILD_DIMS → {UBW_BUILD_FACTS, UBW_ROLLUP_STORAGE_DAILY} → UBW_BUILD_MARTS →
UBW_LOG_RUN. Screenshots are attached to the PR.

## Open items for the data owners

1. **Task graph:** cutover left every `OPS` task suspended. The decision is that cutover leaves the schedule running, so `make sfm-cutover` now resumes the graph after its gate reread passes (`tasks.py resume`, which skips retired tasks). For this run, the graph is resumed only once the run's resource monitor `OW_UBW_SFM_20261013_LV_RM` (5 credits, notify at 75%, suspend at 100%) is confirmed on its warehouse. Bootstrap now creates and re-applies the 75% notify trigger.
2. **`UBW_HOURLY_AUDIT`:** PR #1979 retires it and lands right after #1978 in the merge order, so the two land together. The live `OPS` schema already matches #1979: 10 tasks, no hourly audit.
3. **dbt build logs are not in the repo.** PR #1978 cites `gate/out/dbt/` (`PASS=440 WARN=0 ERROR=0` on each date), but the root `.gitignore` has `*.log`, so the fixture never committed them. They live in the Act 3 session that authored #1978: https://partner-workshops.devinenterprise.com/sessions/860860b4cf89499ca62c760f696cbe52
4. **Merge leftovers.** Stray diff3 markers (`||||||| f77dad4aa`) from #1978's merge were removed from `migration/snowflake/.gitignore` and `README.md`.
5. **First follow-up:** the side-by-side seat column on `/usage` (see above).
