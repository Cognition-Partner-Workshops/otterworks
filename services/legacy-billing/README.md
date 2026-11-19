# Versioned REST foundation

The source of truth is `openapi/billing-v1.yaml` (OpenAPI 3.1). The gateway
forwards `/api/v1/billing` unchanged to `LEGACY_BILLING_URL` (default
`http://legacy-billing:8096`), behind its JWT middleware. No module's v1
operations are implemented yet. Unknown v1 paths already return the JSON
error envelope; legacy routes retain their existing behavior, without new
deprecation headers until converted into adapters.

Modules own `app/v1/{plans,rating,invoicing,dunning}.py`. Each auto-discovered
`register(app, blueprint)` runs after the original legacy routes exist.
Add v1 routes to `blueprint`, and replace the module's legacy callables in
`app.view_functions` by their existing endpoint names (see `app.py`). This
preserves rules and `url_for` names without editing `app.py` or a registry.
Keep adapters and shared module implementation in that module file. Import
`select`/`execute` from `app` inside handlers to avoid initialization cycles.
Shared helpers: `v1.validation` (`required`, `uuid_value`, `date_value`,
`json_body`) and `v1.pagination.paginate` (stable DB order, default 50/max 200).
Raise Werkzeug exceptions for resource lookup failures; v1-only error handling
also maps unique/FK/check violations without exposing SQL.

Run `make billing-contract` (Docker, uv; optional `NS=<unique-name>`). It starts
only Postgres using the procs namespace-derived port scheme in a separate
Compose project, runs pytest and OpenAPI validation, then destroys its volume.
Never point the tests at a shared database: every request drops/reloads the
billing schema, all procedures, and seed. To prepare multi-request state,
use `reset_db` then a raw `app.test_client()` rather than the seeded `client`.

Module tests go in `tests/contract/test_<module>_contract.py`. The
`compare_requests` fixture takes Flask `open` kwargs for legacy and v1,
`unwrap=True` for `data`, `renames={"id": "plan_id"}` (v1 to legacy),
`status_map={201: 200}`, and optional `legacy_body`/`v1_body` extractors for
explicit adapter projections (including redirect/error HTML). Nothing else
is normalized. Pass a deterministic `state_probe()` for mutations: it runs
after each request before the next fresh seed, and both results must match.
Assert legacy errors separately and assert v1's error code/content type.

# Legacy Billing — database-centric before state

`legacy-billing` is a deliberately database-centric billing application. It
is the durable before-state for the stored-procedure extraction flow: the
running application has server-rendered pages and a small JSON API, while the
business behavior is implemented in PostgreSQL under the `billing` schema.

This component is part of the OtterWorks golden app as a durable before-state.
The extraction target and the modern client are separate components and are
not part of this service.

## Modules

### Dunning v1

Dunning is implemented under `/api/v1/billing`: `GET /overdue-invoices`
(required `as_of` query date, paginated), `POST /dunning-schedules` and
`POST /suspensions` (required JSON `as_of` date). Mutation responses are
`201` with `data: {as_of, status}`; these runs have no addressable resource
and therefore no Location header. All domain decisions remain in PL/pgSQL.
Overdue invoice `invoice_id` becomes `id` in v1.

The three `/api/dunning/*` routes are compatibility adapters over the same
implementation, retaining legacy bytes/statuses, form inputs, and the overdue
default date while adding Deprecation and successor-version Link headers.
They retain `invoice_id` and omit the mutation `as_of` echo.
Parity, state, validation, pagination and adapter error tests live in
`tests/contract/test_dunning_contract.py`.

| Module | Procedures/functions | Routes |
|---|---|---|
| Plans | `fn_list_plans`, `fn_entitlement`, `sp_change_plan` | `/plans`, `/plans/<tenant>/entitlement`, `/plans/<tenant>/change` |
| Rating | `fn_usage_rating`, `fn_usage_summary`, `sp_finalize_rating` | v1: `GET /api/v1/billing/tenants/{tenant_id}/rating`, `POST /api/v1/billing/tenants/{tenant_id}/rating-periods`; deprecated adapters: `POST /api/rating/preview`, `POST /api/rating/finalize` |
| Invoicing | `fn_invoice_preview`, `fn_invoice_lines`, `sp_issue_invoice` | `/api/invoices/<tenant>/preview`, `/api/invoices/<tenant>/issue`, `/api/invoices/<invoice>/lines` |
| Dunning | `fn_overdue_accounts`, `sp_schedule_dunning`, `sp_suspend_overdue` | `/api/dunning/overdue`, `/api/dunning/schedule`, `/api/dunning/suspend` |

The Flask layer intentionally binds request values, calls a database
entrypoint, and renders the returned values. It does not reproduce domain
decisions in Python.

### Rating REST migration

Rating's v1 operations are implemented. Preview requires explicit
`period_start` and `period_end` query dates and returns a single `data`
object (no pagination). Finalize requires those dates in a JSON object and
returns `201` with `data` containing tenant, period and finalized status.
Both call the original PL/pgSQL entrypoints; finalization remains an upsert.
There are no rating field renames. Legacy adapters retain their JSON arrays
or status-only bodies, original statuses and error bytes, adding
`Deprecation` and successor-version `Link` headers, including on errors.
No usage-summary HTTP operation is defined by the contract.

## Why it is an extraction candidate

- The domain boundaries are already grouped into database procedure modules.
- The service has a narrow HTTP surface that maps to those entrypoints.
- PostgreSQL owns the state transitions and computed billing results.
- The database can be reset to a deterministic seed for repeatable recordings.

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
before-state.

## Run locally

From the repository root:

```bash
make procs-up NS=dev
curl http://localhost:8096/health
make procs-down NS=dev
```

The Compose profile is intentionally separate from the Helm/EKS path. It
models the legacy application running with its own PostgreSQL database.

## Database layout

- `db/schema.sql` — tables and constraints
- `db/procs/` — database entrypoints
- `db/seed.sql` — deterministic starting state
