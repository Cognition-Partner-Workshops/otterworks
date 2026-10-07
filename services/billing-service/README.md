# Billing Service

This FastAPI service is the extraction target for the plans and dunning
modules. It owns a separate Postgres `billing_svc` schema, keeps the HTTP layer
thin, and places plans and dunning behavior in a plain-Python domain layer.

## Development

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8097
uv run pytest
uv run ruff check app scripts tests
```

The deterministic target seed is generated from
`services/legacy-billing/db/seed.sql`:

```bash
python scripts/generate_seed.py
```

The generated-seed test prevents the target fixture from drifting from the
legacy before-state. `POST /internal/reset` applies every migration in order, truncates
the `billing_svc` schema, and reseeds it so the parity harness can isolate
every scenario.

The reset endpoint is disabled by default. Disposable local/CI Compose stacks
enable it with `BILLING_SVC_ALLOW_INTERNAL_RESET=true`; published deployments
should leave the setting disabled.

The HTTP endpoints are intentionally unauthenticated in this parity fixture.
Authentication and tenant scoping are out of scope here; an extraction that
ships for real must add both at the edge before exposing these endpoints.

For the extracted target, a plan change with an already-scheduled later
subscription preserves that later row. The response's `latest_*` fields always
identify the subscription created by the request, rather than relying on row
ordering.

The legacy procedure attempts a second insert for an identical plan change and
therefore relies on the database uniqueness error. The extracted target returns
HTTP 409 with an explicit conflict detail instead of leaking a 500; this is
target-side error handling, not an additional parity rule.

## Dunning

| Endpoint | Legacy entrypoint |
| --- | --- |
| `GET /api/dunning/overdue?as_of=` | `billing.fn_overdue_accounts` |
| `POST /api/dunning/schedule {as_of}` | `billing.sp_schedule_dunning` |
| `POST /api/dunning/suspend {as_of}` | `billing.sp_suspend_overdue` |

The approved rules are in `procs/rules/dunning.rules.yaml`. These legacy quirks
are copied on purpose and tagged as follow-ups in the ledger: days overdue
count from the issue date; scheduling covers every overdue invoice regardless
of issue date or tenant status; every run appends a new attempt; tenants that
are already suspended are not notified.

`billing_svc.invoices` is a read-only copy of the legacy invoice fixture with
no foreign key to rating tables, so dunning does not depend on the rating
extraction. The schedule response's `last_scheduled` is the last attempt the
run created. When suspending a tenant would hit an active subscription that
starts after `as_of` (legacy fails on the `suspended_on >= starts_on` CHECK),
the target rolls back the whole run and returns HTTP 409. A concurrent
schedule run that collides on `(invoice_id, attempt_no)` also returns HTTP 409.

When using the workshop client with the default disposable stack, the Vite
development proxy forwards `/billing-api/*` to the service on port `12109`.
The billing screens are part of this local parity fixture only. Vite dev
enables their routes by default; a preview requires building with
`VITE_ENABLE_BILLING_FIXTURE=true` and then running `npm run start`. The
`/billing-api` proxy is used by the dev server and by that explicitly flagged
preview. Builds without the flag leave the routes unregistered. No deployed
app or shared-infrastructure deployment is provided for this fixture.
