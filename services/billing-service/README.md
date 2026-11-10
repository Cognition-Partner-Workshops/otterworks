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

Treat this consumer as a separate repository owned by **@otterworks/billing**.
Its nightly invoice export reads TDPROD / FIN_DW using account
`svc_billing_export`; scheduling is external to this service.

```sh
uv sync
uv run python -m app.export_invoices --date 2026-01-06 --out invoices.csv
uv run export-invoices --date 2026-01-06 --out invoices.csv
```

`--date` is the run date: these examples export invoices dated **2026-01-05**.
Omitting it uses Teradata's current date and exports the prior day.
The output includes invoice number, customer name, account number, invoice date,
currency, amount due, tax and open balance, ordered by invoice number/ID.
Open balance subtracts all payments recorded for each invoice at export time;
it is not an historical payment snapshot. No FX conversion is performed.
An empty day writes a header-only CSV. Output replacement is atomic; query or
write failures leave an existing output intact. The output directory must exist.
The export fails rather than silently truncating above 100,000 invoices.

The DAL reads FIN_DW.INVOICE (INVOICE_ID, ACCOUNT_ID, INVOICE_NO, INVOICE_DT,
AMOUNT_DUE, TAX_AMT, CURRENCY_CD), ACCOUNT (ACCOUNT_ID, CUSTOMER_ID, ACCOUNT_NO),
CUSTOMER (CUSTOMER_ID, CUSTOMER_NAME), and PAYMENT (INVOICE_ID, AMOUNT).
It uses Teradata date arithmetic, integer-date floor 1200101 (2020-01-01), and
formatted date/amount output. Monetary values are mapped to exact decimals.
Fake connection settings are in `app/warehouse/config.toml`.
Override the DSN with `FINANCE_WAREHOUSE_DSN`.

The export defaults on. `FINANCE_WAREHOUSE_ENABLED=false` disables it and returns
a nonzero CLI exit code without querying or writing a file. Driver import and
connection creation are deferred until the export is called; the HTTP app's
startup does not connect to Teradata.

### Checks

```sh
uv run pytest
uv run ruff check .
uv run pytest contract
```

Default pytest discovery uses only `tests/`; contract tests are separate.
The contract executes the DAL with the same SQL and run-date parameters through
a warehouse adapter. Default `WAREHOUSE_CONTRACT_TARGET=teradata-emulator`
replays the synthetic recorded-format fixture in
`contract/recorded/teradata/invoice-export.json` and compares row count, invoice
keys, and monetary aggregates against `contract/expected/invoice-export.json`.
Setting TD_EMULATOR_URL selects an explicit stub raising
"emulator endpoint not configured" until the endpoint protocol is available.

For `WAREHOUSE_CONTRACT_TARGET=snowflake`, the placeholder reads
SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE and
SNOWFLAKE_PRIVATE_KEY; missing values skip the contract. With values configured,
it raises an explicit unsupported-operation error until the adapter is finished.
Its destination is SFX_D1110_AFTER.COMPAT, with session QUERY_TAG
`{"run":"sfx-d1110","act":"consumers","consumer":"billing-service"}`.
