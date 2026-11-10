# partner-extract
A separate repository owned by **@otterworks/partner-integrations**.
Nightly at **02:15**, exports yesterday's invoices from TDPROD / FIN_DW using
`svc_partner_sftp`, then prepares a partner SFTP batch. Scheduling is external.

## Run
Requires Bash, GNU date/coreutils, sed, awk and Teradata BTEQ on Linux.
```sh
bin/nightly_extract.sh
bin/nightly_extract.sh 2026-01-05 /existing/output/partner.csv
SFTP_KEY_PATH=/fake/keys/partner_sftp bin/sftp_push.sh /existing/output/partner.csv
```
The date argument is the **invoice date**, defaulting to yesterday in the
process timezone. Only historical dates on/after 2020-01-01 are supported;
the SQL also excludes today/future invoices. Output defaults to
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

Reads:
- INVOICE: INVOICE_ID, ACCOUNT_ID, INVOICE_NO, INVOICE_DT, AMOUNT_DUE, TAX_AMT, CURRENCY_CD.
- ACCOUNT: ACCOUNT_ID, ACCOUNT_NO.
- PAYMENT: INVOICE_ID, AMOUNT.

Open balance subtracts all recorded invoice payments, not only extraction-day
payments. Billing includes tax. The CSV has a column-name header, seven-column
invoice records, then `TRAILER,<row count>,<amount due total>`. Amounts have
two decimal places. Only identifier/date/currency/numeric fields are exported,
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
The default `WAREHOUSE_CONTRACT_TARGET=teradata-emulator` replays synthetic
shared-format JSON through a fake BTEQ and the real nightly/post-processing
pipeline. It checks SQL-template agreement, exact CSV, counts, decimal sums
and invoice keys. `TD_EMULATOR_URL` selects an explicit unsupported stub:
"emulator endpoint not configured".

`WAREHOUSE_CONTRACT_TARGET=snowflake` reads SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER,
SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE and SNOWFLAKE_PRIVATE_KEY. Missing values
produce a clear nonzero exit. Configured values still produce an explicit
unsupported-adapter error; the later adapter must execute the same SQL from
the BTEQ template against SFX_D1110_AFTER.COMPAT with QUERY_TAG
`{"run":"sfx-d1110","act":"consumers","consumer":"partner-extract"}`.
No real Teradata, Snowflake or SFTP execution is claimed by these tests.
