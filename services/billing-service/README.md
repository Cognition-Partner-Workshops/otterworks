# Billing Service

This FastAPI service is the extraction target for the plans module. It owns a
separate Postgres `billing_svc` schema, keeps the HTTP layer thin, and places
plans behavior in a plain-Python domain layer.

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
legacy before-state. `POST /internal/reset` applies the migration, truncates
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

## Finance warehouse consumer

The nightly invoice export reads Snowflake SFX_D1110_AFTER.COMPAT.INVOICE_HDR,
CUSTOMER_ACCOUNT and PAYMENT. Scheduling is external. Set SNOWFLAKE_ACCOUNT,
SNOWFLAKE_USER, SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE and SNOWFLAKE_PRIVATE_KEY
(unencrypted PEM private key). SNOWFLAKE_DATABASE defaults to SFX_D1110_AFTER;
the SQL intentionally uses that database explicitly. Key-pair JWT authentication
is used. FINANCE_WAREHOUSE_ENABLED defaults to true. Driver import and connections
are lazy; HTTP startup opens no warehouse connection. Every session uses UTC and
QUERY_TAG `{"run":"sfx-d1110","act":"consumers","consumer":"billing-service"}`.

```sh
uv run python -m app.export_invoices --date 2026-11-10 --out invoices.csv
```

The date is the run date; BILL_DT on the previous day is exported. Without it,
SQL uses the current UTC date. INVOICE_DT must be at least 2020-01-01.
Accounts join on CUSTOMER_ID; payments aggregate across all dates by INVOICE_ID.
Open balance subtracts payments from TOTAL_AMOUNT. This is not a historical
snapshot or FX-normalized report. CSV columns and Decimal values are preserved.
An empty export writes only the header; atomic replacement preserves prior files
on failure. More than 100000 invoices fails rather than truncates. The destination
directory must exist.

```sh
uv run pytest
uv run ruff check .
WAREHOUSE_CONTRACT_TARGET=replay uv run pytest contract
WAREHOUSE_CONTRACT_TARGET=snowflake uv run pytest contract -s
```

Contracts are excluded from ordinary discovery. Replay uses unchanged recorded
JSON and frozen legacy SQL in contract/teradata_reference.py. The teradata-emulator
and snowflake-semantics targets use ../../consumers/contract-kit. For live emulator
comparisons set TD_USER=svc_exit_parity, ROWS_PER_TABLE=800, BUSINESS_DATE=20261109,
TD_PG_PORT and CONTRACT_KIT_PYTHON. TD_EMULATOR_HOME overrides the runtime path.
CONTRACT_RECORD=true records the baseline; review expected keys, counts and sums.

The Snowflake target skips without credentials or the connector. It forces
SFX_D1110_PARITY_WH (SNOWFLAKE_CONTRACT_WAREHOUSE may explicitly name that same
warehouse), prints every query ID and issues SELECTs only. It compares column
labels, overlapping invoice keys, dates and currencies to the recorded fixture,
then independently cross-checks counts and Decimal totals against RAW_BILLING.
The larger Snowflake seed has 20,100 accounts and 66,667 matching invoices versus
the 800-row emulator seed's 267 matching invoices. Customer names, account numbers
and amounts intentionally differ for overlapping keys. Snowflake FM amount strings
are trimmed (e.g. 0.00), unlike padded Teradata FORMAT strings; from_values parses
both as Decimal.
