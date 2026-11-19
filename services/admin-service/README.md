# Finance operations admin dashboard

Separate repository owned by **@otterworks/finance-ops**. The JWT-protected
GET /api/v1/admin/finance/dashboard requires a nonempty string subject and the
`super_admin` or `admin` role from the verified JWT's `role` or `roles` claims
(including the auth-service's uppercase `ADMIN`). Missing subjects receive 401;
other or missing roles receive 403 before cache or warehouse access. It returns
DSO, AR open balance, last-30-day
collections and the ten highest overdue accounts. The finance:refresh_dashboard
rake task refreshes the one-hour Rails cache; scheduling is external. Disabled
access is 404; warehouse errors are sanitized 503s. Empty data yields zero metrics
and an empty list. The planted production configuration is unchanged.

The fake plaintext ODBC DSN in config/finance_warehouse.yml points to TDPROD /
SFX_BILLING as svc_admin_fin. FINANCE_WAREHOUSE_DSN overrides it.
FINANCE_WAREHOUSE_ENABLED defaults true. Boot never loads ODBC or connects;
connections are per query. Install optional ruby-odbc and native unixODBC in
warehouse-enabled deployments (bundle config set with teradata; bundle install).
Ordinary frozen CI installations omit the optional driver.

## Data and metrics

All sources use real SFX_BILLING DDL:
- GL_JOURNAL_LINE (GL_ACCOUNT_ID, DEBIT_AMOUNT, CREDIT_AMOUNT) and GL_ACCOUNT
  (GL_ACCOUNT_ID, ACCOUNT_NUMBER): AR is net debit-minus-credit on account 1200.
- INVOICE_HDR (INVOICE_DT, TOTAL_AMOUNT): trailing 30-day billed total, less
  CREDIT_NOTE (CREDIT_DT, AMOUNT) credits in that window, is the DSO denominator.
  DSO = AR / net billed * 30; zero denominator yields zero. GL and credit sources
  overlap this account's DBQL reports.
- PAYMENT (INVOICE_ID, PAYMENT_DT, AMOUNT): trailing 30-day cash collections and
  independently aggregated all-time invoice payments.
- CUSTOMER_ACCOUNT (CUSTOMER_ID, ACCOUNT_NUMBER, ACCOUNT_NAME) joins invoice
  CUSTOMER_ID for the overdue list. Net-30 due dates are INVOICE_DT + 30 because
  the schema has no DUE_DT. Overdue balances subtract payments from invoice totals;
  unlike the ledger summary, this operational list does not allocate credit notes.

The dashboard retains its existing cross-currency totals without FX conversion;
consumers must not interpret them as a currency-normalized financial statement.
SQL keeps SEL, TOP 10, ZEROIFNULL, NULLIFZERO, CURRENT_DATE - 30, 1200101,
DATE FORMAT and QUALIFY ROW_NUMBER. The API's legacy field names remain stable.

### Checks

```sh
bundle exec rspec
```
