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
  account 1200, matched with UPPER(RTRIM(ACCOUNT_NUMBER)) to preserve Teradata's
  case-insensitive, trailing-pad comparison and align with report-service.
- COMPAT.INVOICE_HDR (INVOICE_DATE, TOTAL_AMOUNT): trailing 30-day billed total,
  less CORE_BILLING.STG_BILLING__CREDIT_NOTE (CREDIT_DT, AMOUNT) credits in that
  window, is the DSO denominator. DSO = AR * 30 / net billed; a zero denominator
  yields zero.
- COMPAT.PAYMENT (INVOICE_HDR_ID, PAYMENT_DATE, AMOUNT): trailing 30-day cash
  collections and all-time payments per invoice. The COMPAT INVOICE_HDR_ID key
  coalesces INVOICE_HDR_ID and INVOICE_ID; retain that key so payments carrying
  only INVOICE_HDR_ID are included. Other clients joining raw INVOICE_ID need
  their own changes.
- COMPAT.CUSTOMER_ACCOUNT joins invoice CUSTOMER_ID for the overdue list. Net-30
  due dates are INVOICE_DATE + 30 days. Overdue balances subtract payments from
  invoice totals and do not allocate credit notes.

These definitions are inherited from Teradata. The dashboard and report-service
use GL account 1200 for AR; legacy-billing AR aging and finance-notebook use
invoice totals minus payments. Those balances need not match. The notebook's
monthly DSO is not comparable to this dashboard's trailing-30-day GL-AR DSO.

The 30-day windows end at CURRENT_DATE (UTC) unless DashboardQueries is given an
`as_of:` date, which is bound as a statement parameter. Totals are not
FX-converted. The original Teradata SQL is kept, unchanged, in contract/legacy/
for emulator parity runs only; production never sends it.
Each explicit business date has its own one-hour cache entry, separate from the
undated API dashboard.

## Open target data gaps — merge blocked

[Upstream #2669](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2669)
must serve the invoiced totals and GL postings from the shared 200k seed before
this consumer can merge. The PR stays draft until the live contract passes.
AR, billed, DSO and overdue differences are target data gaps, not an accepted
seed difference. The recorded 200k emulator parity run used
TD_USER=svc_exit_parity and BUSINESS_DATE=20261109:

| Metric | 200k emulator | Live gap observed in cross-check |
|---|---:|---:|
| GL 1200 AR | 77,512,580.24 | 4,647,025.23 |
| Billed in 30 days | 77,844,053.16 | 32,857,603.85 |
| Credits in 30 days | 335,677.72 | 335,677.72 |
| Collections in 30 days | 27,892,499.60 | 27,892,499.60 |
| DSO | 30.00162749 | about 4.3 |

Live COMPAT.INVOICE_HDR.TOTAL_AMOUNT equals SUBTOTAL_AMOUNT + TAX_AMOUNT on all
200,100 invoice rows (total 32,875,202.55), before P_MONTHLY_INVOICE recalculates
the invoiced amounts from lines. GL account 1200 postings also diverge. These
gaps affect both DSO inputs and the overdue balances and top-10 membership.
The client cannot repair the upstream data; no compensating constants or
alternate AR formula are used here. After #2669 is corrected, rerun the strict
live gate and compare overdue members/balances with the same-seed emulator.

Deployment also needs SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE and
SNOWFLAKE_PRIVATE_KEY injected into the service environment by the deployment
owner. The existing deployment scripts do not supply them; those scripts and
Helm configuration are outside this client folder. Missing credentials produce
the sanitized 503 described above.

## Checks and contracts

```sh
RAILS_ENV=test bundle exec rails db:schema:load
RAILS_ENV=test bundle exec rspec
WAREHOUSE_CONTRACT_TARGET=replay bundle exec rspec contract
WAREHOUSE_CONTRACT_TARGET=snowflake bundle exec rspec contract/snowflake_live_contract_spec.rb --format documentation
```

Unit specs use PostgreSQL 15; contract specs need no Rails database.

- replay: recorded Teradata results in contract/recorded/teradata, checked against
  contract/expected; these are separate from the shared-seed live reference.
- teradata-emulator / snowflake-semantics: send contract/legacy/*.sql through
  ../../consumers/contract-kit (see its README for TD_PG_PORT and
  CONTRACT_KIT_PYTHON). Run parity sessions as TD_USER=svc_exit_parity.
- snowflake: contract/snowflake_live_contract_spec.rb runs the production SQL on
  live Snowflake (SFX_D1110_AFTER.COMPAT, SFX_D1110_PARITY_WH) for business date
  2026-11-09, prints the query IDs, and checks via QUERY_HISTORY that each one ran
  with the consumer query tag on the parity warehouse. It skips when the
  Snowflake credentials are absent, whatever the target.

The shared-seed reference, tolerances and open #2669 gaps are recorded in
contract/expected/snowflake-live.json. The live contract checks AR, collections,
billed and credits within 0.01 and DSO within 0.0001 of that emulator run. It
prints aggregate-only live output and query IDs. It must fail while the upstream
gap remains; positive AR/DSO and shape checks alone cannot establish parity.
A green unit/replay CI run with the credential-gated live job skipped is not
approval to merge.
