# Legacy Billing

`legacy-billing` is a database-centric billing application: the running
application has server-rendered pages and a small JSON API, while the
business behavior is implemented in PostgreSQL under the `billing` schema.

This service is the current system of record for billing. An extraction
effort toward a modern service is in progress; the extraction target and the
modern client are separate components and are not part of this service.

## OW_BILLING estate on PostgreSQL (takeout from Oracle)

The connected-estate overlay (`docker-compose.tp.yml`) now runs the OW_BILLING
estate on PostgreSQL 15 with `BILLING_BACKEND=ow_billing_pg`: database
`ow_tp_billing`, schema `ow_billing`, in its own container
(`docker-compose.billing-postgres.yml`, `localhost:55433`), separate from the
shared infra Postgres. DDL and the PL/pgSQL ports of the `PKG_*` packages are
in `db/postgres/initdb/`; the backend is `app/backends/ow_billing_pg.py`.

```bash
make billing-pg-up                    # Postgres target
make billing-pg-migrate               # reload every table from Oracle (idempotent)
make billing-pg-recon NS=demo         # counts, money sums, key coverage -> docs/tech-partnerships/recon/
make billing-char-capture URL=http://127.0.0.1:8096   # replay the characterization scenario
make billing-char-parity NS=demo      # grade it against tests/characterization/golden/oracle.json
```

Invoice lines whose header does not exist in Oracle (37 `DEMO-GHOST-*` lines
in `NS=demo`) are kept unchanged in `invoice_line_orphan` with a
`quarantine_reason`, held for Finance review; `invoice_line` carries a real
foreign key to `invoice_header`. Month-end totals exclude them exactly as the
Oracle inner join did. `GET /api/reports/reconciliation` on Postgres
recomputes its checks against the Oracle figures captured at migration time
in `migration_baseline`.

`BILLING_BACKEND=oracle` remains the rollback path while the Oracle estate
exists.

## Oracle backend and billing facade

`BILLING_BACKEND=oracle` selects the Oracle backend. In either estate mode the API gateway routes
`/api/v1/billing` here and supplies trusted `X-User-ID`, `X-User-Email`, and
`X-User-Roles` identity headers. The facade exposes plans, the signed-in
tenant, entitlement, plan changes, usage, invoices, customer fields, and admin
overdue/dunning views under `/api/v1/billing`. Estate failures return the
estate-unavailable response rather than falling back to another backend. After
`make tp-month-end NS=<ns>`, the batch-derived finance result is available at
`GET /api/reports/finance?ns=<ns>`.

## Modules

| Module | Procedures/functions | Routes |
|---|---|---|
| Plans | `fn_list_plans`, `fn_entitlement`, `sp_change_plan` | `/plans`, `/plans/<tenant>/entitlement`, `/plans/<tenant>/change` |
| Rating | `fn_usage_rating`, `fn_usage_summary`, `sp_finalize_rating` | `/api/rating/preview`, `/api/rating/finalize` |
| Invoicing | `fn_invoice_preview`, `fn_invoice_lines`, `sp_issue_invoice` | `/api/invoices/<tenant>/preview`, `/api/invoices/<tenant>/issue`, `/api/invoices/<invoice>/lines` |
| Dunning | `fn_overdue_accounts`, `sp_schedule_dunning`, `sp_suspend_overdue` | `/api/dunning/overdue`, `/api/dunning/schedule`, `/api/dunning/suspend` |

The Flask layer binds request values, calls a database entrypoint, and
renders the returned values. It does not reproduce domain decisions in
Python.

## Why it is an extraction candidate

- The domain boundaries are already grouped into database procedure modules.
- The service has a narrow HTTP surface that maps to those entrypoints.
- PostgreSQL owns the state transitions and computed billing results.
- The database can be reset to a deterministic seed for repeatable
  verification runs.

## Full verification loop

The extracted reference service is `services/billing-service/`, backed by a
separate Postgres database and `billing_svc` schema. The
declarative contract and human-approved ledger live under `procs/`. From the
repository root:

```bash
make procs-up NS=dev
make procs-rules-gate MODULE=plans
make procs-parity NS=dev
make procs-down NS=dev
```

The parity report compares the target's returned fields and target-side state
probes with immutable recordings. Modules not yet extracted remain skipped.
The legacy procedure files and recordings remain the source of truth for the
existing behavior.

## Run locally

From the repository root:

```bash
make procs-up NS=dev
curl http://localhost:8096/health
make procs-down NS=dev
```

The Compose profile is separate from the Helm/EKS path. It models the
application running with its own PostgreSQL database.

## Usage bridge

The optional `usage-bridge` consumes the `otterworks-events` SNS topic through
the `otterworks-billing-usage` SQS queue and posts billable activity to
`legacy-billing` asynchronously. Document creation, document updates, and
comments count as one `api` unit; file uploads count as `storage` units
rounded up to megabytes with a minimum of one; file updates count as one
`compute` unit. Other event types are discarded.

Each usage event ID is a canonical 36-character UUID5 of
`ow-usage:<event_type>:<entity_id>:<timestamp>`, so redelivery is handled as a
duplicate by the billing facade rather than billed twice. Recorded and
duplicate responses are deleted from SQS. The bridge authenticates to
`POST /internal/usage/events` with the `USAGE_INTERNAL_TOKEN` environment
variable. Invalid requests and missing or incorrect tokens (`400`, `401`) are
logged and dropped; an unset token returns `503` and Oracle or other `5xx`
failures remain visible for visibility-timeout retry without blocking the
publishing service. The endpoint rejects bodies over 16 KB and validates the
tenant/event identifiers, usage kind, unit range, and ISO-8601 timestamp before
opening an Oracle connection.

## Database layout

- `db/schema.sql` — tables and constraints
- `db/procs/` — database entrypoints
- `db/seed.sql` — deterministic starting state
