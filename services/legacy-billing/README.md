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

### Databricks live target (dbx-d1111)

Set `FINANCE_WAREHOUSE_TARGET=databricks` to select the native AR aging DAL.
Connections remain lazy. The query reads the existing `billing__v_account_invoices`,
`billing__customer_account` and `billing__payment` objects in
`cpw.dbx_d1111_after`; no compatibility objects or infrastructure are created.
`FINANCE_WAREHOUSE_AS_OF=2026-11-09` pins the application date for comparisons;
without it the date is evaluated on each request.

The native rewrite replaces SEL/TOP, ZEROIFNULL/NULLIFZERO and integer date
arithmetic with SELECT/LIMIT, COALESCE and explicit DATE/date_add/datediff.
The Teradata `1200101` floor is `DATE '2020-01-01'`. Grouped text is right-trimmed
as in the bridge; account names/numbers retain case, while the Latin currency
code uses `UTF8_LCASE` for NOT CASESPECIFIC grouping and ordering. Joins use
numeric identifiers. DATE values and decimal sums use the existing response
mapper. Only OPEN_RATIO is computed from the two exact warehouse sums in Python:
this preserves PostgreSQL bridge numeric-division precision instead of Spark's
reduced decimal scale. The internal denominator never enters the public response.

This on-request, consumer-owned query is best protected by a native rewrite:
a compatibility view cannot translate client SEL/TOP/FORMAT or date arithmetic,
and changing a shared view would affect other readers. The current live data
has 2,000 generated rows per main entity plus fixture additions. Its expected
result is separate from the existing 800-row replay contract, which is retained.

From the repository root, with the five DATABRICKS_HOST/TOKEN/WAREHOUSE_ID/CATALOG/
RUN_TOKEN variables securely supplied (`cpw`, `dbx-d1111` only):

```sh
python3 -m venv /path/to/legacy-billing-venv
/path/to/legacy-billing-venv/bin/pip install -r services/legacy-billing/requirements-contract.txt
make sfx-teradata-up NS=dbx-d1111-consumers-legacy-billing ROWS_PER_TABLE=2000 BUSINESS_DATE=20261109
export TD_PG_PORT=$(NS=dbx-d1111-consumers-legacy-billing python3 -c 'import os,zlib; print(54500+zlib.crc32(os.environ["NS"].encode())%1000)')
cd services/legacy-billing
/path/to/legacy-billing-venv/bin/pytest
WAREHOUSE_CONTRACT_TARGET=replay /path/to/legacy-billing-venv/bin/pytest contract
WAREHOUSE_CONTRACT_TARGET=databricks /path/to/legacy-billing-venv/bin/pytest -s contract
```

The live target clearly skips when secrets are missing, with no replay fallback.
It pins both paths to 2026-11-09, proves counts and order-independent SHA256 of
all columns in CUSTOMER_ACCOUNT, INVOICE_HDR, PAYMENT and V_ACCOUNT_INVOICES
across the emulator/before/after, then compares every ordered output field with
the original Teradata SQL through the shared bridge and with checked-in expected
keys, sums and full result hash. Canonical hashes encode nulls distinctly, dates
as ISO, exact numerics without scale-only differences, and right-trimmed strings
to remove CHAR storage padding. Duplicates remain in the hash input.
Set `LEGACY_BILLING_EVIDENCE=/absolute/path/result.json` to save proof and statement
IDs. The consumer workflow runs this target only when all five GitHub secrets
are configured and seeds an isolated Docker emulator.

**Cutover remains red:** DBQL records INVOICE_EXPORT_QUEUE reads, but no such
object exists in either live schema inventory and no queue SQL exists in this
consumer. A target read fails TABLE_OR_VIEW_NOT_FOUND. A safe implementation
needs the source definition and ownership decision; AR aging parity alone
does not retire this account's Teradata dependency. No empty view is substituted.
