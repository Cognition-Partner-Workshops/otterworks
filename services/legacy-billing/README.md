# Legacy Billing

`legacy-billing` is a database-centric billing application: the running
application has server-rendered pages and a small JSON API, while the
business behavior is implemented in PostgreSQL under the `billing` schema.

This service is the current system of record for billing. An extraction
effort toward a modern service is in progress; the extraction target and the
modern client are separate components and are not part of this service.

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

### Storage backend

`BILLING_BACKEND` selects where the Flask routes read from:

- `postgres`: the PL/pgSQL functions and procedures in `db/`. Run with
  `make procs-up NS=<ns> BILLING_BACKEND=postgres`; the mongo service is then
  not started.
- `mongo` (default): the migrated `ow_billing` database (`MONGO_URI`, `MONGO_DB`).
  `make procs-up` enables the `mongo` Compose profile, which starts a `mongo:7`
  service on `127.0.0.1:${PROCS_MONGO_PORT}`. The read routes (`/`, `/plans`,
  `/plans/<tenant>/entitlement`, `/api/invoices/<tenant>/preview`,
  `/api/invoices/<invoice>/lines`, `/api/dunning/overdue`, and the
  `/api/rating/preview` POST) return the same JSON as the Postgres functions.
  The write routes (`/plans/<tenant>/change`, `/api/rating/finalize`,
  `/api/invoices/<tenant>/issue`, `/api/dunning/schedule`,
  `/api/dunning/suspend`) still go through PostgreSQL procedures and answer
  `501` on the mongo backend.

`/health` reports which backend is active. Rollback is
`BILLING_BACKEND=postgres` and a restart; no data moves.

## Database layout

- `db/schema.sql` — tables and constraints
- `db/procs/` — database entrypoints
- `db/seed.sql` — deterministic starting state
