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
AR aging reads Snowflake SFX_D1110_AFTER.COMPAT with net-30 aging, returning
up to 100 account/currency balances. Set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER,
SNOWFLAKE_ROLE and SNOWFLAKE_PRIVATE_KEY (unencrypted PEM) for JWT key-pair
authentication, plus SNOWFLAKE_WAREHOUSE. SNOWFLAKE_DATABASE overrides the
default session database SFX_D1110_AFTER; the query uses fully qualified tables.
Sessions use UTC and query tag
`{"run":"sfx-d1110","act":"consumers","consumer":"legacy-billing"}`.

```sh
pip install -r requirements-dev.txt
pytest
WAREHOUSE_CONTRACT_TARGET=replay pytest contract -rs
WAREHOUSE_CONTRACT_TARGET=snowflake pytest contract -s
```

Contract tests are excluded from default discovery. Replay, teradata-emulator
(the default), and snowflake-semantics retain the contract-only legacy SQL and
the shared kit at ../../consumers/contract-kit. Recorded/expected fixtures cover
the original 800-row estate and remain unchanged. The live Snowflake contract
uses the production client, SFX_D1110_PARITY_WH and SFX_D1110_AFTER, checking
columns, formatting, ordering and reconciliation rather than exact fixture sums
or keys. It skips without the four authentication variables, regardless of
target, and prints the query id with pytest -s.
