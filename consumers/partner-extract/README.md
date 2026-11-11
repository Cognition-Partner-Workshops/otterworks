# partner-extract
A separate repository owned by **@otterworks/partner-integrations**.
Nightly at **02:15**, exports yesterday's invoices from TDPROD / SFX_BILLING using
`svc_partner_sftp`, then prepares a partner SFTP batch. Scheduling is external.

## Run
Requires Bash, GNU date/coreutils, sed, awk and Teradata BTEQ on Linux.
```sh
bin/nightly_extract.sh
bin/nightly_extract.sh 2026-01-05 /existing/output/partner.csv
SFTP_KEY_PATH=/fake/keys/partner_sftp bin/sftp_push.sh /existing/output/partner.csv
```
The date argument is the **billing date**, defaulting to yesterday in the
process timezone. Only historical dates on/after 2020-01-01 are supported;
the SQL also excludes today/future billing dates. Output defaults to
partner-invoices-YYYY-MM-DD.csv in the current directory. The parent directory
must already exist. Rendered SQL/report files are private temporary files,
removed on exit. BTEQ failures or malformed reports do not replace an existing
CSV. There is no retry or scheduler installation.

`sql/partner_invoice_extract.bteq` is the canonical inline Teradata query and
contains an obviously fake .LOGON/password. The script substitutes a Teradata
integer date and export filename, invokes `BTEQ_BIN` (default bteq) through
stdin, and passes its exported report to the same post-processor used by
contracts. Do not enable shell tracing with real credentials.
Set `FINANCE_WAREHOUSE_ENABLED=false` to skip execution (default true).
Nothing connects on import/startup outside explicit script execution.

Reads real SFX_BILLING sources:
- V_INVOICE_BASE (INVOICE_ID) joined to INVOICE_HDR (INVOICE_ID, CUSTOMER_ID,
  INVOICE_NUMBER, INVOICE_DT, BILL_DT, TOTAL_AMOUNT, TAX_AMOUNT, CURRENCY_CD).
- CUSTOMER_ACCOUNT (CUSTOMER_ID, ACCOUNT_NUMBER).
- PAYMENT (INVOICE_ID, AMOUNT).
Headers, the invoice-base view and payments overlap this account's DBQL reports.
SQL retains LOCKING ROW FOR ACCESS, SEL, ZEROIFNULL, FORMAT date/amount casts,
the substituted 1YYMMDD date, 1200101 and CURRENT_DATE - 1.

Open balance subtracts all recorded invoice payments, not only extraction-day
payments. Billing includes tax. The CSV has a column-name header, seven-column
invoice records, then `TRAILER,<row count>,<amount due total>`. Amounts are normalized to
two decimal places, including reports that omit the zero before the decimal. Only identifier/date/currency/numeric fields are exported,
so no unescaped free-text CSV fields are permitted. Duplicate invoice numbers,
unexpected BTEQ headings and malformed rows fail closed. Blank report lines
are ignored. Credits are supported; totals use integer cents with an absolute
9,000,000,000,000-cent safety limit for each amount and running total.
Trailer totals assume one reporting currency; no FX conversion is performed.

## SFTP stub
`SFTP_DRY_RUN=1` is the default. The stub prints an sftp command and stdin
batch for `partner@sftp.partner.example`, using `SFTP_KEY_PATH` (default fake
path /fake/keys/partner_sftp), and `SFTP_REMOTE_DIR` (default /incoming).
It never opens a network connection. Setting SFTP_DRY_RUN to any other value
fails explicitly; live transfer is intentionally not implemented.
Quotes, backslashes and newlines in batch paths are rejected.

## Checks
```sh
bash tests/run.sh
bash contract/run.sh
docker run --rm -v "$PWD":/work -w /work koalaman/shellcheck:stable bin/*.sh tests/*.sh contract/*.sh
```
Units use an injectable fake BTEQ; no extra test dependencies.
Contracts additionally require Python 3's standard library for JSON and Decimal.
The default `WAREHOUSE_CONTRACT_TARGET=teradata-emulator` executes the exact
rendered BTEQ SQL LIVE through ../contract-kit, then passes its report rows
through the real nightly/post-processing pipeline and dry-run SFTP stub.
It checks template agreement, exact CSV, counts, decimal sums and invoice keys.
Follow the kit README for emulator setup (ROWS_PER_TABLE=800,
BUSINESS_DATE=20261109), bridge dependencies, TD_PG_PORT and CONTRACT_KIT_PYTHON.
The runtime defaults to this repository; TD_EMULATOR_HOME overrides it.
CONTRACT_RECORD=true bash contract/run.sh re-records exact live JSON; review
expected CSV, counts, sums and keys after changes.
WAREHOUSE_CONTRACT_TARGET=replay bash contract/run.sh needs only Python's standard
library, no emulator or bridge dependencies, and runs in a dedicated CI job.
snowflake-semantics invokes the shared live bridge.
Unit fake-BTEQ outputs/expectations are separate from live contract fixtures.

`WAREHOUSE_CONTRACT_TARGET=snowflake` reads SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER,
SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE and SNOWFLAKE_PRIVATE_KEY. Missing values
produce a clear nonzero exit. Configured values still produce an explicit
unsupported-adapter error; the later adapter must execute the same SQL from
the BTEQ template against SFX_D1110_AFTER.COMPAT with QUERY_TAG
`{"run":"sfx-d1110","act":"consumers","consumer":"partner-extract"}`.
Live contracts exercise the local emulator, not a Teradata ODBC/native BTEQ driver.
No Snowflake or SFTP network execution is performed.

## Databricks target (run dbx-d1111)
`WAREHOUSE_CONTRACT_TARGET=databricks bash contract/run.sh` runs the real nightly
pipeline with `BTEQ_BIN=bin/databricks_bteq.sh`: the rendered BTEQ script is
validated against the template, then `sql/partner_invoice_extract.databricks.sql`
(native Databricks rewrite) reads cpw.dbx_d1111_after through
`databricks_warehouse.py` and writes the same report rows into the shared
post-processor. Needs DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_WAREHOUSE_ID
and the connector from ../contract-kit/requirements-databricks.txt; without
them it prints `SKIP databricks contract: ...` and exits 0.
It compares byte-for-byte with `contract/expected/dbx-baseline`, the old
Teradata path recorded on an emulator seeded to equal cpw.dbx_d1111_before
(`make sfx-teradata-up NS=dbx-d1111-consumers-partner-extract ROWS_PER_TABLE=2000`,
then `CONTRACT_DATASET=dbx-baseline bash contract/run.sh`).
`python contract/input_equality.py` proves those inputs equal (count + sorted-row
sha256 per table). CURRENT_DATE is pinned on both paths with
PARTNER_EXTRACT_AS_OF_DATE (default 2026-11-10 for billing date 2026-11-09);
production leaves it unset so Databricks uses current_date().
