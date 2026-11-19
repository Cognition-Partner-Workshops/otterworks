# Report service

## Finance warehouse consumer

Treat this consumer as a separate repository owned by **@otterworks/finance-reporting**.
It reads TDPROD / SFX_BILLING using Teradata account `svc_report_recon`, on demand
(and is intended for daily 06:00 invocation by an external scheduler; none is installed here).

`GET /api/v1/reports/finance-reconciliation?period=202611` returns JSON with
`period`, `invoicedTotal`, `paidTotal`, `arGlBalance`, `variance` and
`unreconciledInvoices`. Period must be YYYYMM. Invalid input returns 400;
warehouse failures return 503. Set `finance.warehouse.enabled=false` to remove
the endpoint and warehouse bean. The flag defaults on; creating the Spring
context does not open a warehouse connection. Fake TD connection settings live in
`src/main/resources/com/otterworks/report/financewarehouse/teradata.properties`;
override with Spring properties for deployment. Runtime driver:
`com.teradata.jdbc.TeraDriver` through JDBC service discovery.

### Schema and reconciliation
This is a monthly **activity** reconciliation, not a cumulative AR aging report.
All tables below are in SFX_BILLING:
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
with all-date payment totals. SFX_BILLING has no due-date column: this report uses
a **net-30 policy**, due date = INVOICE_DT + 30 days. Invoices must be more than
30 days past that derived due date. The API retains its existing invoiceNo,
accountNo, invoiceDate, daysOverdue, amountDue and paid fields, mapped from
INVOICE_NUMBER, ACCOUNT_NUMBER, formatted INVOICE_DT, derived days overdue,
TOTAL_AMOUNT and summed AMOUNT. Ordering is days overdue descending, then INVOICE_ID.
An empty result is an empty list. No CSV endpoint is provided.

SQL retains LOCKING ROW FOR ACCESS, SEL, TOP 25, ZEROIFNULL, EXTRACT, integer
date arithmetic (`CURRENT_DATE - 30`), a 1200101 date floor (2020-01-01), and
DATE FORMAT casts. The account's DBQL report inventory also reads INVOICE_HDR.

### Checks

```sh
mvn -B test
```
