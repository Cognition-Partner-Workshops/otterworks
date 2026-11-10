# Report service

## Finance warehouse consumer

Treat this consumer as a separate repository owned by **@otterworks/finance-reporting**.
It reads TDPROD / FIN_DW using Teradata account `svc_report_recon`, on demand
(and is intended for daily 06:00 invocation by an external scheduler; none is installed here).

`GET /api/v1/reports/finance-reconciliation?period=202601` returns JSON with
`period`, `invoicedTotal`, `paidTotal`, `arGlBalance`, and `variance`.
The period must be YYYYMM. Invalid input returns 400; warehouse failures return 503.
Set `finance.warehouse.enabled=false` to remove the endpoint and warehouse bean.
The flag defaults on; creating the Spring context does not open a warehouse connection.
Fake TD connection settings live next to the DAL in
`src/main/resources/com/otterworks/report/financewarehouse/teradata.properties`;
override them with Spring properties for a real deployment. The runtime driver is
`com.teradata.jdbc.TeraDriver`, loaded through JDBC service discovery.

This is a monthly **activity** reconciliation, not a cumulative AR aging report:
- FIN_DW.INVOICE: INVOICE_DT, AMOUNT_DUE (invoice total, already including tax).
- FIN_DW.PAYMENT: PAYMENT_DT, AMOUNT (all payments posted in the selected month,
  including settlement of earlier invoices).
- FIN_DW.GL_JOURNAL: PERIOD_ID, GL_ACCOUNT_CD, DEBIT_AMT, CREDIT_AMT
  (AR account 112000, debits minus credits in the selected accounting period).
- Variance = invoiced total minus paid total minus AR GL movement.
Independent aggregates prevent invoice/payment/journal join fan-out. Empty periods
return one zero-valued row. Amounts are exact decimals; the warehouse is assumed to
use a single reporting currency (there is no FX conversion).
The migration ledger in the existing `reconciliation` package is unrelated and unchanged.

The same response includes `unreconciledInvoices`: up to 25 underpaid invoices
from the requested invoice month, with due dates more than 30 days before today.
Payments are summed over all dates for each invoice (not just the activity month).
The list includes invoice/account numbers, formatted invoice date, days overdue,
amount due and paid total, ordered by days overdue descending then invoice ID.
This second query joins FIN_DW.ACCOUNT (ACCOUNT_ID, ACCOUNT_NO), INVOICE
(INVOICE_ID, ACCOUNT_ID, INVOICE_NO, INVOICE_DT, DUE_DT, AMOUNT_DUE) and PAYMENT
(INVOICE_ID, AMOUNT). It uses Teradata TOP 25, integer date arithmetic, a
1200101 integer date floor (2020-01-01), and a DATE FORMAT cast.
An empty result is an empty list. No CSV endpoint is provided.
The contract profile checks both queries, including the invoice fixture's ordered
invoice keys and amount aggregates; overdue-day fixtures represent a fixed recorded date.

### Checks

From this directory, with Maven and Java 8:
```sh
mvn -B test
mvn -B -Pcontract test
mvn -B checkstyle:check
```

Without local Maven, use:
```sh
docker run --rm -v "$PWD":/w -v "$HOME/.m2":/root/.m2 -w /w maven:3.9-eclipse-temurin-8 mvn -B test
docker run --rm -v "$PWD":/w -v "$HOME/.m2":/root/.m2 -w /w maven:3.9-eclipse-temurin-8 mvn -B -Pcontract test
```

Default unit tests use mocked JDBC and a fake DAL and exclude the contract package.
The contract profile runs only the contract test. Default
`WAREHOUSE_CONTRACT_TARGET=teradata-emulator` replays
`contract/recorded/teradata/finance-reconciliation.json` and compares row count and
all monetary aggregates with `contract/expected/finance-reconciliation.json`.
These are synthetic recorded-format fixtures, not evidence of a live Teradata query.
If TD_EMULATOR_URL is set, the adapter explicitly raises
"emulator endpoint not configured" until the emulator protocol is available.
The contract passes the exact DAL SQL constant and period to the selected adapter.

For `WAREHOUSE_CONTRACT_TARGET=snowflake`, the placeholder reads
SNOWFLAKE_ACCOUNT, USER, ROLE, WAREHOUSE, PRIVATE_KEY (each with the SNOWFLAKE_ prefix);
missing values skip cleanly. With them present it explicitly fails as unsupported
until the official Snowflake JDBC adapter is installed. Its destination constants
are SFX_D1110_AFTER.COMPAT and its session QUERY_TAG is
`{"run":"sfx-d1110","act":"consumers","consumer":"report-service"}`.
The later migration worker must execute the supplied DAL SQL there and finish the adapter.
