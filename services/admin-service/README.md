# Finance operations admin dashboard

Separate repository owned by **@otterworks/finance-ops**. The JWT-protected
GET /api/v1/admin/finance/dashboard returns DSO, AR open balance, last-30-day
collections and the ten highest overdue accounts. The finance:refresh_dashboard
rake task refreshes the one-hour Rails cache; scheduling is external. Disabled
access is 404; warehouse errors are sanitized 503s. Empty data yields zero metrics
and an empty list. The planted production configuration is unchanged.

The dashboard reads Snowflake database SFX_D1110_AFTER on warehouse
SFX_D1110_PARITY_WH through FinanceWarehouse::SnowflakeClient, which calls the
Snowflake SQL API v2 with key-pair JWT auth (the jwt gem; no native driver).
Credentials come from SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE and
SNOWFLAKE_PRIVATE_KEY; database, schema, warehouse, query tag and timeout live in
config/finance_warehouse.yml (SNOWFLAKE_DATABASE, SNOWFLAKE_WAREHOUSE and
SNOWFLAKE_QUERY_TAG override them). Every statement carries query tag
`{"run":"sfx-d1110","act":"consumers","consumer":"admin-service"}` and runs in
UTC. Missing credentials or any API error surface as the sanitized 503.
FINANCE_WAREHOUSE_ENABLED defaults true. Boot never connects; each query is one
SQL API statement. The service no longer connects to Teradata.

## Data and metrics

- COMPAT.GL_JOURNAL_LINE and COMPAT.GL_ACCOUNT: AR is net debit-minus-credit on
  account 1200.
- COMPAT.INVOICE_HDR (INVOICE_DATE, TOTAL_AMOUNT): trailing 30-day billed total,
  less CORE_BILLING.STG_BILLING__CREDIT_NOTE (CREDIT_DT, AMOUNT) credits in that
  window, is the DSO denominator. DSO = AR * 30 / net billed; a zero denominator
  yields zero.
- COMPAT.PAYMENT (INVOICE_HDR_ID, PAYMENT_DATE, AMOUNT): trailing 30-day cash
  collections and all-time payments per invoice.
- COMPAT.CUSTOMER_ACCOUNT joins invoice CUSTOMER_ID for the overdue list. Net-30
  due dates are INVOICE_DATE + 30 days. Overdue balances subtract payments from
  invoice totals and do not allocate credit notes.

The 30-day windows end at CURRENT_DATE (UTC) unless DashboardQueries is given an
`as_of:` date, which is bound as a statement parameter. Totals are not
FX-converted. The original Teradata SQL is kept, unchanged, in contract/legacy/
for emulator parity runs only; production never sends it.

## Checks and contracts

```sh
RAILS_ENV=test bundle exec rails db:schema:load
RAILS_ENV=test bundle exec rspec
WAREHOUSE_CONTRACT_TARGET=replay bundle exec rspec contract
```

Unit specs use PostgreSQL 15; contract specs need no Rails database.

- replay: recorded Teradata results in contract/recorded/teradata, checked against
  contract/expected (recorded at ROWS_PER_TABLE=800, BUSINESS_DATE=20261109).
- teradata-emulator / snowflake-semantics: send contract/legacy/*.sql through
  ../../consumers/contract-kit (see its README for TD_PG_PORT and
  CONTRACT_KIT_PYTHON). Run parity sessions as TD_USER=svc_exit_parity.
- snowflake: contract/snowflake_live_contract_spec.rb runs the production SQL on
  live Snowflake (SFX_D1110_AFTER.COMPAT, SFX_D1110_PARITY_WH) for business date
  2026-11-09, prints the query IDs, and checks via QUERY_HISTORY that each one ran
  with the consumer query tag on the parity warehouse. It skips when the
  Snowflake credentials are absent, whatever the target.

What must agree with the emulator, and the intended differences, are recorded in
contract/expected/snowflake-live.json.
