# Finance operations admin dashboard

Separate repository owned by **@otterworks/finance-ops**. The JWT-protected
GET /api/v1/admin/finance/dashboard returns DSO, AR open balance, last-30-day
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

## Checks and contracts

```sh
RAILS_ENV=test bundle exec rails db:schema:load
RAILS_ENV=test bundle exec rspec
WAREHOUSE_CONTRACT_TARGET=replay bundle exec rspec contract
```

Unit specs use PostgreSQL 15; contract specs are isolated from ordinary discovery
and need no Rails database. Default teradata-emulator executes both DAL SQL
constants LIVE through ../../consumers/contract-kit. Follow its README for
runtime/seed setup (ROWS_PER_TABLE=800, BUSINESS_DATE=20261109), TD_PG_PORT,
bridge dependencies and CONTRACT_KIT_PYTHON. TD_EMULATOR_HOME optionally overrides
the default repository-root runtime. CONTRACT_RECORD=true bundle exec rspec contract
records the live JSON; review expected counts, sums and keys after changes.

Replay needs no Python/warehouse and runs in a dedicated CI job.
snowflake-semantics invokes the shared live bridge. snowflake is an explicit
placeholder: missing SNOWFLAKE_ACCOUNT, USER, ROLE, WAREHOUSE or PRIVATE_KEY
skips; configured execution is unsupported. Destination metadata:
SFX_D1110_AFTER.COMPAT, query tag
`{"run":"sfx-d1110","act":"consumers","consumer":"admin-service"}`.
