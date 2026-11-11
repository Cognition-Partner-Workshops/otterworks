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

Separate repository owned by **@otterworks/legacy-billing**. The default-on
FINANCE_WAREHOUSE_ENABLED flag exposes /finance/ar-aging as JSON, or
?format=html as an escaped table. Invalid formats return 400; disabled returns
404, warehouse failures a sanitized 503. Startup opens no warehouse connection.
The fake plaintext DSN in app/finance_warehouse.ini uses svc_legacy_billing
against TDPROD / SFX_BILLING; FINANCE_WAREHOUSE_DSN can override it.

The query reads V_ACCOUNT_INVOICES (CUSTOMER_ID, INVOICE_ID, INVOICE_DT,
CURRENCY_CD, TOTAL_AMOUNT), CUSTOMER_ACCOUNT (CUSTOMER_ID, ACCOUNT_NUMBER,
ACCOUNT_NAME), and PAYMENT (INVOICE_ID, AMOUNT). All tables/views are in
SFX_BILLING, overlapping the service account's DBQL view.
There is no due-date column; net-30 terms derive DUE_DT = INVOICE_DT + 30.
Open balance subtracts all payments from invoice totals, then groups by account
and currency into current, 1–30, 31–60, 61–90 and over-90 buckets.
Up to 100 accounts are ordered by open balance, account number and currency.
Empty results are an empty list/table. No FX conversion is performed.
SQL retains SEL, TOP 100, ZEROIFNULL, NULLIFZERO, integer date arithmetic,
the 1200101 floor and DATE FORMAT cast. Driver import is lazy.

```sh
pip install -r requirements-dev.txt
pytest
WAREHOUSE_CONTRACT_TARGET=replay pytest contract
```
The contract directory is excluded from default discovery. The default
teradata-emulator target runs the DAL's actual SQL through the shared kit at
../../consumers/contract-kit. Follow its README for emulator setup, Python bridge
dependencies, TD_PG_PORT and CONTRACT_KIT_PYTHON. TD_EMULATOR_HOME optionally
overrides the runtime's default repository root.
CONTRACT_RECORD=true pytest contract records live output, then checks expected
counts, account keys, sums and bucket reconciliation. Fixtures use the seeded
800-row estate (BUSINESS_DATE=20261109). Review expectations after changes.
Replay requires neither a warehouse nor bridge dependencies and runs in CI.
snowflake-semantics uses the same shared live bridge. snowflake remains an
explicit placeholder: missing SNOWFLAKE_ACCOUNT, USER, ROLE, WAREHOUSE or
PRIVATE_KEY skips, while configured execution is unsupported.
Destination metadata: SFX_D1110_AFTER.COMPAT, query tag
`{"run":"sfx-d1110","act":"consumers","consumer":"legacy-billing"}`.
