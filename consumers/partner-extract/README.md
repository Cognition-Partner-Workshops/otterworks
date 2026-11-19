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
stdin, and validates its exported report before publishing the CSV.
The [example crontab](../../warehouse/teradata/jobs/crontab.example) uses the
local warehouse's BTEQ emulator. Do not enable shell tracing with real credentials.
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

### Checks

```sh
bash tests/run.sh
```
