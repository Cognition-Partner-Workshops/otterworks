# Legacy Billing — database-centric before state

`legacy-billing` is a deliberately database-centric billing application. It
is the durable before-state for the stored-procedure extraction flow: the
running application has server-rendered pages and a small JSON API, while the
business behavior is implemented in PostgreSQL under the `billing` schema.

This component is part of the OtterWorks golden app as a durable before-state.
The extraction target and the modern client are separate components and are
not part of this service.

## Modules

| Module | Procedures/functions | Routes |
|---|---|---|
| Plans | `fn_list_plans`, `fn_entitlement`, `sp_change_plan` | `/plans`, `/plans/<tenant>/entitlement`, `/plans/<tenant>/change` |
| Rating | `fn_usage_rating`, `fn_usage_summary`, `sp_finalize_rating` | `/api/rating/preview`, `/api/rating/finalize` |
| Invoicing | `fn_invoice_preview`, `fn_invoice_lines`, `sp_issue_invoice` | `/api/invoices/<tenant>/preview`, `/api/invoices/<tenant>/issue`, `/api/invoices/<invoice>/lines` |
| Dunning | `fn_overdue_accounts`, `sp_schedule_dunning`, `sp_suspend_overdue` | `/api/dunning/overdue`, `/api/dunning/schedule`, `/api/dunning/suspend` |

The Flask layer intentionally binds request values, calls a database
entrypoint, and renders the returned values. It does not reproduce domain
decisions in Python.

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

## Finance warehouse consumer

This consumer is treated as a separate repository owned by
**@otterworks/legacy-billing**. It reads TDPROD / FIN_DW on request with account
`svc_legacy_billing`.

- `GET /finance/ar-aging` returns JSON.
- `GET /finance/ar-aging?format=html` renders an accounts-receivable table.
- `FINANCE_WAREHOUSE_ENABLED=false` disables both representations (404).
  It defaults on. Unsupported formats return 400; warehouse failures return a
  sanitized 503 response.

The report shows the top 100 outstanding account balances, separately by currency,
with current/not-yet-due, 1–30, 31–60, 61–90 and over-90-day buckets.
Aging is based on the warehouse's current date. Open balance subtracts all
recorded payments; credit balances and fully paid invoices are excluded.
The oldest due date and open-to-invoiced amount ratio are also included.
Invoice dates before 2020-01-01 are excluded. No FX conversion is performed.
The list is a top-account view, not a complete general-ledger reconciliation.
Empty results are an empty JSON list or a table with an empty-state message.

The DAL reads FIN_DW.INVOICE (INVOICE_ID, ACCOUNT_ID, INVOICE_DT, DUE_DT,
CURRENCY_CD, AMOUNT_DUE), PAYMENT (INVOICE_ID, AMOUNT), ACCOUNT (ACCOUNT_ID,
CUSTOMER_ID, ACCOUNT_NO) and CUSTOMER (CUSTOMER_ID, CUSTOMER_NAME).
Teradata SQL is inline in `app/finance_warehouse.py`.
Fake connection settings are adjacent in `app/finance_warehouse.ini`; override
the DSN with `FINANCE_WAREHOUSE_DSN`. Driver import and connection creation happen
only when the report is requested, never at application import/startup.
The Flask warehouse dependency is injectable through
`app.extensions["finance_warehouse"]`.

### Checks

From this service directory with Python 3.12:

```sh
python -m pip install -r requirements-dev.txt
pytest
python -m pyflakes app tests contract
pytest contract
```

Default pytest discovery runs only `tests/`, with fake warehouses and database
connections. The separate contract command runs the actual DAL SQL through a
warehouse adapter, then checks row count, ordered account keys, bucket totals
and open-balance aggregates. The default
`WAREHOUSE_CONTRACT_TARGET=teradata-emulator` replays the synthetic recorded
result in `contract/recorded/teradata/ar-aging.json` against
`contract/expected/ar-aging.json`. Recorded buckets reflect a fixed capture date.
Setting TD_EMULATOR_URL selects a stub that explicitly raises
"emulator endpoint not configured" pending the endpoint protocol.

`WAREHOUSE_CONTRACT_TARGET=snowflake` reads SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER,
SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE and SNOWFLAKE_PRIVATE_KEY. Missing values skip
the contract; configured values currently raise an explicit unsupported-operation
error until the adapter is implemented. Its destination constants are
SFX_D1110_AFTER.COMPAT and session QUERY_TAG
`{"run":"sfx-d1110","act":"consumers","consumer":"legacy-billing"}`.
