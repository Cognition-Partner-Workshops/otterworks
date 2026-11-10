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

Owned by **@otterworks/billing** as a separate repository. The nightly invoice
export reads TDPROD / SFX_BILLING as svc_billing_export; scheduling is external.
Fake plaintext DSN: app/warehouse/config.toml (override FINANCE_WAREHOUSE_DSN).
The default-on FINANCE_WAREHOUSE_ENABLED flag gates exports. Driver import and
connections are lazy; HTTP startup opens no warehouse connection.

```sh
uv run python -m app.export_invoices --date 2026-11-10 --out invoices.csv
```
The date is the run date; BILL_DT on the previous day is exported. Without it,
SQL uses CURRENT_DATE - 1. CSV retains invoice_no, customer_name, account_no,
invoice_date, currency_cd, amount_due, tax_amt and open_balance. Invoice number,
account name and account number come from INVOICE_HDR.INVOICE_NUMBER and
CUSTOMER_ACCOUNT.ACCOUNT_NAME/ACCOUNT_NUMBER joined on CUSTOMER_ID.
INVOICE_HDR supplies BILL_DT, INVOICE_DT, CURRENCY_CD, TOTAL_AMOUNT and TAX_AMOUNT.
PAYMENT (INVOICE_ID, AMOUNT) is aggregated across all dates and subtracted for
open balance. This is not a historical snapshot or FX-normalized report.
SQL keeps SEL, TOP 100001, ZEROIFNULL, integer date arithmetic, 1200101 and
FORMAT date/amount casts. The account's DBQL inventory also reads headers/payments.

An empty export writes only the CSV header. Atomic output replacement preserves
prior files on failure. Above 100000 invoices the export fails rather than truncates.
The destination directory must exist.

```sh
uv run pytest
uv run ruff check .
WAREHOUSE_CONTRACT_TARGET=replay uv run pytest contract
```
Contracts are excluded from ordinary discovery. The default teradata-emulator
target executes the DAL SQL LIVE through ../../consumers/contract-kit.
Seed the emulator with ROWS_PER_TABLE=800, BUSINESS_DATE=20261109; install kit
dependencies and set TD_PG_PORT and CONTRACT_KIT_PYTHON for the live environment.
The runtime defaults to this repository; TD_EMULATOR_HOME overrides it.
Parameters are bound client-side as escaped SQL literals before invoking the kit.

```sh
CONTRACT_RECORD=true uv run pytest contract
```
Records exact live JSON under contract/recorded/teradata. Review expected keys,
counts and sums after changes. Replay requires no warehouse or bridge dependencies
and runs in CI's contract-replay job. snowflake-semantics uses the shared live bridge.
The snowflake target remains an explicit placeholder (missing SNOWFLAKE_ACCOUNT,
USER, ROLE, WAREHOUSE or PRIVATE_KEY skips; configured execution is unsupported).
Destination metadata: SFX_D1110_AFTER.COMPAT, QUERY_TAG
`{"run":"sfx-d1110","act":"consumers","consumer":"billing-service"}`.
