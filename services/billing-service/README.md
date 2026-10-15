# Billing Service

This FastAPI service is the extraction target for the plans, rating and
invoicing modules. It persists to the MongoDB `billing_migration` database
(collections `plans`, `tenants` with embedded `creditNotes`, `subscriptions`,
`usageEvents`, `ratingPeriods` with the embedded `rating` result and `invoices`
with embedded `invoiceLines` and `dunningAttempts`, per mapping spec v2), keeps
the HTTP layer thin, and places the behavior in a plain-Python domain layer.

## Development

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8097
uv run pytest
uv run ruff check app tests
```

`BILLING_SVC_MONGODB_URI` names the cluster and `BILLING_SVC_MONGODB_DATABASE`
the database (default `billing_migration`). Plan changes run in a multi-document
transaction, so the deployment must be a replica set (Atlas, or the single-node
`billing-service-mongo` set in `docker-compose.procs.yml`).

`app/load.py` loads the collections from the legacy PostgreSQL, creating the
spec's indexes and validators. Secrets are passed by environment variable name
only; `--collections` restricts a run to one batch's write targets:

```bash
uv run python -m app.load --source-dsn-secret POSTGRESQL_RO_DSN --target-uri-secret MONGODB_ATLAS_URI \
    --collections invoices
```

Rating (`GET .../rating`, `GET .../usage-summary`, `POST .../rating-periods`)
sums `usageEvents` and the prior periods' rollover with aggregation pipelines
and reads plans and subscriptions only through the plans repository. Money is
`Decimal` end to end (`Decimal128` in MongoDB) and rounded half away from zero
like PostgreSQL `round(numeric, 2)`. Finalizing a period is idempotent: the
period keeps its id, its single `rating` subdocument keeps its id, first
subscription, quota and `createdAt`, and a re-run overwrites only used, rollover,
billable and overage; the response is the persisted result.

Invoicing (`GET .../invoice-preview`, `POST .../invoices`,
`GET /api/invoices/{id}/lines`) owns `invoices`. Issuing an invoice is one
transaction: the rating period is finalized through the rating module, the
invoice and its lines are one document upsert keyed by the legacy
`md5(period_id || 'invoice')` id (a re-issue keeps the row, resets the status
and replaces the lines), and the applied credit is drawn down through the plans
repository's `apply_credit` because `tenants.creditNotes` belongs to the plans
unit. The preview returns the function's exact numerics (the two tax halves are
not rounded until they are issued). `MongoInvoicingRepository.append_dunning_attempt`
is the owner API the dunning module uses to push into `invoices.dunningAttempts`,
idempotent on `(invoiceId, attemptNo)`.

`POST /internal/reset` runs the same load from `BILLING_SVC_SOURCE_DSN` (the
disposable Compose stack's legacy database) so the parity harness can isolate
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
