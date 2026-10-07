# Billing Service

This FastAPI service is the extraction target for the plans and rating modules.
It owns a separate Postgres `billing_svc` schema, keeps the HTTP layer thin, and
places plans and rating behavior in a plain-Python domain layer.

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
legacy before-state. `POST /internal/reset` applies the migrations, truncates
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

When using the workshop client with the default disposable stack, the Vite
development proxy forwards `/billing-api/*` to the service on port `12109`.
The billing screens are part of this local parity fixture only. Vite dev
enables their routes by default; a preview requires building with
`VITE_ENABLE_BILLING_FIXTURE=true` and then running `npm run start`. The
`/billing-api` proxy is used by the dev server and by that explicitly flagged
preview. Builds without the flag leave the routes unregistered. No deployed
app or shared-infrastructure deployment is provided for this fixture.

## Rating

| Legacy entrypoint | Target endpoint |
| --- | --- |
| `billing.fn_usage_rating` | `GET /api/tenants/{tenant_id}/usage-rating?period_start=&period_end=` |
| `billing.fn_usage_summary` | `GET /api/tenants/{tenant_id}/usage-summary?period_start=&period_end=` |
| `billing.sp_finalize_rating` | `POST /api/tenants/{tenant_id}/rating-finalizations` |

The rules are `RATING-R01` to `RATING-R10` in `procs/rules/rating.rules.yaml`.
The extraction copies legacy behaviour, including the 101-unit first tier, the
gross rollover sum, the suspended-share proration with double rounding, and
PostgreSQL's numeric quotient precision (`pg_numeric_quotient`). Those quirks
are recorded as follow-ups in the ledger rather than changed here.

When no subscription overlaps the period, both rating and finalization return
HTTP 404 (approved in `RATING-R01`); the legacy function returns a row of nulls
and the legacy finalize fails on a NOT NULL constraint. Finalizing a period that
already exists under an id other than `md5(tenant_id || period_start)` returns
HTTP 409, where the legacy procedure fails on the foreign key.
