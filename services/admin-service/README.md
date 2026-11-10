# Admin service

Rails 7.1 API service for OtterWorks administration.

## Finance warehouse consumer

Treat this consumer as a separate repository owned by **@otterworks/finance-ops**.
It reads TDPROD / FIN_DW using Teradata account `svc_admin_fin`.

`GET /api/v1/admin/finance/dashboard` returns DSO, AR open balance, collections
over the last 30 days and the top ten overdue accounts. The route uses the
existing JWT middleware; send an Authorization bearer token as for other admin
endpoints. Amounts and DSO are decimal strings, not binary floating-point values.
Set `FINANCE_WAREHOUSE_ENABLED=false` to disable the endpoint (404) and task.
Warehouse/driver failures return a sanitized 503.
The flag defaults on, but no driver is loaded or warehouse connection opened at boot.

The dashboard uses:
- FIN_DW.INVOICE: INVOICE_ID, ACCOUNT_ID, INVOICE_DT, DUE_DT, AMOUNT_DUE.
- FIN_DW.PAYMENT: INVOICE_ID, PAYMENT_DT, AMOUNT.
- FIN_DW.ACCOUNT: ACCOUNT_ID, CUSTOMER_ID, ACCOUNT_NO.
- FIN_DW.CUSTOMER: CUSTOMER_ID, CUSTOMER_NAME.

AR open balance sums positive invoice balances after all recorded payments,
excluding invoices before 2020-01-01. DSO is AR open balance divided by billed
amount over the last 30 days, multiplied by 30; no billing activity returns zero.
Collections use payment dates in that same window. Overdue accounts include
invoices due before today, ordered by total overdue amount then account number.
The model assumes one reporting currency; no FX conversion is performed.

```sh
bundle exec rake finance:refresh_dashboard
```

Run this task hourly from an external scheduler. It recomputes both queries,
updates the one-hour dashboard cache, and prints the refreshed JSON.
The endpoint fills the same cache on a miss. Persistence/sharing of the cache
depends on the Rails cache store; a null store does not retain it across calls.

### ODBC setup

Fake connection settings are in `config/finance_warehouse.yml`. Override the full
connection string with `FINANCE_WAREHOUSE_DSN`. The client lazily requires
`odbc` and uses the native Teradata ODBC driver through unixODBC.

The `ruby-odbc` gem is locked in an **optional** Bundler group, excluded from
ordinary install and CI. A warehouse-enabled runtime must install unixODBC
development headers, the Teradata ODBC driver/DSN, then opt into the group:

```sh
bundle config set --local with teradata
bundle install
```

The fake DSN alone cannot connect to a live warehouse.

### Checks

With Ruby 3.3, PostgreSQL 15 and RAILS_ENV=test, configure DATABASE_HOST,
DATABASE_PORT, DATABASE_USER and DATABASE_PASSWORD for the test database:

```sh
bundle install
bundle exec rails db:schema:load
bundle exec rspec
bundle exec rspec contract
```

Default RSpec discovery runs only `spec/`. Unit/request specs use a fake ODBC
client and the existing JWT helper. Contract specs in `contract/` run separately
without Rails or PostgreSQL. Default `WAREHOUSE_CONTRACT_TARGET=teradata-emulator`
replays synthetic recorded results in `contract/recorded/teradata/` and checks
row counts, account keys and monetary aggregates against `contract/expected/`.
The adapter receives the exact SQL constants used by the dashboard.
TD_EMULATOR_URL selects a stub that explicitly raises
"emulator endpoint not configured" until the endpoint protocol is available.

`WAREHOUSE_CONTRACT_TARGET=snowflake` reads SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER,
SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE and SNOWFLAKE_PRIVATE_KEY. Missing values skip
the specs; configured values currently raise an explicit unsupported-operation
error pending adapter implementation. Destination constants are
SFX_D1110_AFTER.COMPAT and session QUERY_TAG
`{"run":"sfx-d1110","act":"consumers","consumer":"admin-service"}`.
