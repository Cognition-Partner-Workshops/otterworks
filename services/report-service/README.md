# Report service

## Finance warehouse consumer

Treat this consumer as a separate repository owned by **@otterworks/finance-reporting**.
It reads Snowflake SFX_D1110_AFTER.COMPAT on demand
(and is intended for daily 06:00 invocation by an external scheduler; none is installed here).

`GET /api/v1/reports/finance-reconciliation?period=202611` returns JSON with
`period`, `invoicedTotal`, `paidTotal`, `arGlBalance`, `variance` and
`unreconciledInvoices`. Period must be YYYYMM. Invalid input returns 400;
warehouse failures return 503. Set `finance.warehouse.enabled=false` to remove
the endpoint and warehouse bean. The flag defaults on; creating the Spring
context does not open a warehouse connection. Configure SNOWFLAKE_ACCOUNT,
SNOWFLAKE_USER, SNOWFLAKE_ROLE and SNOWFLAKE_PRIVATE_KEY (unencrypted PKCS#8 PEM)
through environment variables or Spring properties. JDBC uses JWT key-pair authentication,
database SFX_D1110_AFTER. Set finance.warehouse.warehouse (default: SNOWFLAKE_WAREHOUSE)
for production compute. Live contracts explicitly use only SFX_D1110_PARITY_WH.
Every session sets QUERY_TAG to exactly
`{"run":"sfx-d1110","act":"consumers","consumer":"report-service"}`.

### Schema and reconciliation
This is a monthly **activity** reconciliation, not a cumulative AR aging report.
All production views below are in SFX_D1110_AFTER.COMPAT:
- INVOICE_HDR: INVOICE_ID, CUSTOMER_ID, INVOICE_NUMBER, INVOICE_DT, TOTAL_AMOUNT
  (invoice total including tax).
- PAYMENT: INVOICE_ID, PAYMENT_DT, AMOUNT (all payments in the selected month,
  including settlement of earlier invoices).
- GL_JOURNAL_LINE: GL_ACCOUNT_ID, POSTING_DT, DEBIT_AMOUNT, CREDIT_AMOUNT.
- GL_ACCOUNT: GL_ACCOUNT_ID, ACCOUNT_NUMBER (AR account 1200).
- CUSTOMER_ACCOUNT: CUSTOMER_ID, ACCOUNT_NUMBER.

Independent invoice, payment and journal aggregates prevent join fan-out.
AR GL movement is debits minus credits posted in the selected month.
Variance = invoice total minus paid total minus AR GL movement; mismatches are
reported, not suppressed. Empty periods produce a zero-valued summary.
Amounts are exact decimals. There is no FX conversion; these totals assume one
reporting currency. The seeded estate contains multiple currencies, so its
contract aggregates are mechanical control totals, not an FX-normalized ledger.
The unrelated migration ledger in the existing `reconciliation` package is unchanged.

The second query lists up to 25 underpaid invoices from the selected invoice month,
with all-date payment totals. The original report uses
a **net-30 policy**, due date = INVOICE_DT + 30 days. Invoices must be more than
30 days past that derived due date. The API retains its existing invoiceNo,
accountNo, invoiceDate, daysOverdue, amountDue and paid fields, mapped from
INVOICE_NUMBER, ACCOUNT_NUMBER, formatted INVOICE_DT, derived days overdue,
TOTAL_AMOUNT and summed AMOUNT. Ordering is days overdue descending, then INVOICE_ID.
An empty result is an empty list. No CSV endpoint is provided.

Both queries prefer COMPAT: all required legacy columns, including GL_ACCOUNT,
exist in the live schema. The backing CORE_BILLING views are named STG_BILLING__*,
not bare table names. No native fallback is needed.
SQL drops LOCKING, translates SEL to SELECT, TOP to ordered LIMIT, ZEROIFNULL
to COALESCE, date arithmetic to DATEADD/DATEDIFF, FORMAT to TO_CHAR and the
1200101 date floor to DATE '2020-01-01'. GL account matching uses UPPER/RTRIM
to preserve case-insensitive, trailing-blank-insensitive comparisons.
Live GL account numbers are four-character numeric strings, including exact '1200'.
Legacy *_DT columns are fully populated and are intentionally used instead of *_DATE.
The source SQL remains test-only for emulator comparisons.

### Checks
From this directory with Maven and Java 8:
```sh
mvn -B test
WAREHOUSE_CONTRACT_TARGET=replay mvn -B -Pcontract test
```
Unit tests use mocked JDBC/fake DALs and exclude the contract package.
The contract profile runs only contract tests; CI additionally runs replay in
the contract-replay job without credentials or a warehouse.

For live contracts, first follow `../../consumers/contract-kit/README.md` to
use the repository's warehouse/teradata runtime, seed the emulator with ROWS_PER_TABLE=800,
BUSINESS_DATE=20261109, and install the Python bridge dependencies.
Then (adjust paths/port for your namespace):
```sh
export TD_EMULATOR_HOME=/home/ubuntu/sfx/td # optional separate-worktree override
export TD_PG_PORT=54902
export CONTRACT_KIT_PYTHON=/path/to/contract-venv/bin/python
TD_USER=svc_exit_parity mvn -B -Pcontract test
TD_USER=svc_exit_parity WAREHOUSE_CONTRACT_TARGET=snowflake-semantics mvn -B -Pcontract test
```
The default target is **teradata-emulator**, executed LIVE through the shared
Python bridge. There is no fallback if the emulator is unavailable.
CONTRACT_KIT_BRIDGE optionally overrides the bridge file path.
The adapter substitutes each integer period parameter as a validated integer
literal before sending the exact DAL SQL; production still uses JDBC binds.

The reconciliation fixture uses November 2026, exercising billed amounts,
payments and AR journal postings. The ordered unreconciled fixture uses
January 2026, exercising historical underpaid invoices. Expected files assert
row counts, keys and monetary sums. Days overdue depends on CURRENT_DATE and
is not an aggregate assertion. Recordings were captured from the seeded emulator,
not handwritten; compare them with expected files after intentional changes.
To re-record through the same Java adapter and bridge:
```sh
CONTRACT_RECORD=true mvn -B -Pcontract test
```
This writes both live query outputs under contract/recorded/teradata/ using the
kit's --record option. Existing assertions still run; inspect any mismatches and
review expected values rather than blindly accepting new outputs.
Replay reads these JSON files locally and needs neither Python nor a database.

WAREHOUSE_CONTRACT_TARGET supports teradata-emulator, replay,
snowflake-semantics (live, case-sensitive string comparisons), and snowflake.
The live Snowflake target executes the production SQL through JDBC and prints query IDs:
```sh
WAREHOUSE_CONTRACT_TARGET=snowflake mvn -B -Pcontract test
```
Missing SNOWFLAKE_ACCOUNT, USER, ROLE or PRIVATE_KEY cleanly skips the tests.
Live contracts assert exact columns/order, integer period/day fields, ISO dates,
two-place decimal strings, reconciliation arithmetic, underpayment, the 25-row cap
and ordering by days overdue descending then the actual invoice ID (looked up
read-only). They compare against contract/recorded/snowflake, excluding dynamic
DAYS_OVERDUE. Set SNOWFLAKE_CONTRACT_RECORD=true to explicitly refresh those
baselines after reviewing a data change; normal test runs never write fixtures.

The emulator replay uses an 800-rows-per-table seed, while Snowflake uses the shared
200k seed (seed 1110, with supplemental journal rows). Thus monetary totals and
the eligible invoice set differ; contract/expected and the emulator replay remain
unchanged. The live January 2026 list has 16 rows versus 17 in replay: key
INV-2026-9000000028 is absent. The other keys retain the same account/date and PAID=0,
but TOTAL_AMOUNT differs. The contract asserts account/date/paid agreement on
every shared key, rather than asserting identical keys or invoice totals.
DAYS_OVERDUE follows CURRENT_DATE, not the recording date.

The Snowflake JDBC 3.24.2 driver targets Java 8 (class-file major version 52).
The emulator adapter always uses the reserved svc_exit_parity account.
