# partner-extract

Nightly at 02:15, exports yesterday's billed invoices from Snowflake and
prepares a dry-run SFTP batch. Scheduling is external.

## Run

Requires Linux, Bash, GNU date/coreutils, awk and Python 3.
Install `python3 -m pip install -r requirements.txt`.
Set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE,
SNOWFLAKE_PRIVATE_KEY (unencrypted PEM, never enable shell tracing), and
SNOWFLAKE_WAREHOUSE. JWT key-pair authentication uses database SFX_D1110_AFTER,
schema COMPAT, session TIMEZONE UTC, and exactly this QUERY_TAG:
`{"run":"sfx-d1110","act":"consumers","consumer":"partner-extract"}`.

```sh
bash bin/nightly_extract.sh
bash bin/nightly_extract.sh 2026-01-05 /existing/output/partner.csv
```

The date is the billing date, default yesterday in the process timezone.
Dates must be valid ISO dates on/after 2020-01-01; SQL excludes current/future
billing dates. Output defaults to partner-invoices-YYYY-MM-DD.csv; its parent
must exist. Temporary reports are private and removed on exit. Export failures
or malformed rows preserve existing output; publishing is atomic before SFTP.
FINANCE_WAREHOUSE_ENABLED=false skips execution. PARTNER_EXTRACT_PYTHON selects
Python; WAREHOUSE_EXPORT_BIN is an optional executable accepting date and report
filename, used by tests/contracts. No connection is made on Python import.
The exporter prints each query ID to stderr.

## Reads and output

Production SQL is sql/partner_invoice_extract.sql, one statement using a
connector pyformat bound ISO date (not string interpolation). It reads only
SFX_D1110_AFTER.COMPAT.CUSTOMER_ACCOUNT, INVOICE_HDR and PAYMENT.
The invoice-base view is inlined as CUSTOMER_ACCOUNT joined to INVOICE_HDR
on CUSTOMER_ID. Open balance subtracts all recorded payments, not just those
on the extraction day. Amount due includes tax.

CSV has the fixed seven-column header, invoice records, and
TRAILER,<count>,<amount due sum>. The unchanged numeric normalization supports
credits and omitted leading zeroes, rejects duplicates, malformed rows,
overflow and headings, and ignores blank report lines. Each amount and running
total has an absolute 9,000,000,000,000-cent limit. No FX conversion is done.

## SFTP stub

SFTP_DRY_RUN=1 is the default and only supported mode; no transfer occurs.
SFTP_KEY_PATH defaults to /fake/keys/partner_sftp; SFTP_REMOTE_DIR to /incoming.
The stub prints the batch for the existing fake SFTP endpoint.
Quotes, backslashes and newlines in batch paths are rejected.

## Contracts and checks

```sh
bash tests/run.sh
WAREHOUSE_CONTRACT_TARGET=replay bash contract/run.sh
WAREHOUSE_CONTRACT_TARGET=snowflake bash contract/run.sh
```

Unit tests use a fake exporter. Replay needs only stdlib Python and preserves
exact recorded CSV, counts, sums and keys. The old BTEQ template is only a parity
reference at contract/teradata/partner_invoice_extract.bteq, with fake logon.
contract/teradata_export.sh renders its 1YYMMDD integer date and report path
for warehouse_bteq.py, which checks template agreement through the shared kit.
teradata-emulator (default) and snowflake-semantics retain the shared bridge
behaviour and use TD_USER=svc_exit_parity. Follow ../contract-kit/README.md
for emulator dependencies (800-row seed, BUSINESS_DATE=20261109), TD_PG_PORT,
TD_EMULATOR_HOME and CONTRACT_KIT_PYTHON. CONTRACT_RECORD=true records fixtures.

The live snowflake target skips successfully if account, user, role or key is
missing. Otherwise it forces SFX_D1110_PARITY_WH, uses the real nightly exporter
with SFTP dry-run, checks formats/header/trailer, recorded key inclusion and
ordering, date/currencies, and exact Decimal count/sums against an independent
RAW_BILLING.INVOICE_HDR / CUSTOMER_ACCOUNT / PAYMENT query. Both recorded and
Snowflake report rows must pass the production postprocessor. All statements
are reads; query IDs are printed.

Intended differences:
- Teradata FORMAT emits .00, Snowflake emits 0.00; postprocess normalizes both.
- ORDER BY UPPER(INVOICE_NUMBER), INVOICE_NUMBER preserves Teradata
  NOT CASESPECIFIC ordering.
- CURRENT_DATE uses session UTC, rather than the Teradata server timezone.
- LOCKING ROW FOR ACCESS is dropped in favour of Snowflake MVCC.
- The rendered 1YYMMDD integer becomes a bound ISO DATE.
- Snowflake holds the full shared seed: 66,667 invoices billed 2026-11-09,
  versus 267 matching invoices in the 800-row emulator seed. The first 267
  sorted keys agree, but amounts need not: INV-2026-0000001 is 336.63 live
  versus 419.96 recorded. Live sums therefore compare to native Snowflake,
  never row-for-row to emulator amounts.
