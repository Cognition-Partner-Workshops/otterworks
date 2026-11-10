# bi-semantic
A separate repository owned by **@otterworks/bi**. Looker connection
`tdprod_fin` reads TDPROD / FIN_DW as `svc_bi_semantic`; see connection.md
for fake connection settings and the default-on access flag.

## Model
Invoice explore joins accounts and customers with many-to-one relationships.
Payments and GL journal are independent explores; journal joins GL accounts.
The overdue-account PDT rebuilds every four hours and includes the top 100
accounts with positive invoice balances overdue by more than 30 days.
All payments per invoice offset its balance. Invoice history starts 2020-01-01.
Amounts assume one reporting currency. Invoice billing includes tax.

Read columns:
- INVOICE: INVOICE_ID, ACCOUNT_ID, INVOICE_NO, INVOICE_DT, DUE_DT, AMOUNT_DUE, TAX_AMT.
- PAYMENT: PAYMENT_ID, INVOICE_ID, PAYMENT_DT, AMOUNT.
- ACCOUNT: ACCOUNT_ID, CUSTOMER_ID, ACCOUNT_NO, PLAN_NAME.
- CUSTOMER: CUSTOMER_ID, CUSTOMER_NAME, REGION_CODE.
- GL_JOURNAL: JOURNAL_ID, GL_ACCOUNT_CD, PERIOD_ID, DEBIT_AMT, CREDIT_AMT.
- GL_ACCOUNT: GL_ACCOUNT_CD, GL_ACCOUNT_NAME, ACCOUNT_CLASS.

## Checks
```sh
python -m pip install -r requirements-dev.txt
python -m pytest
python -m pytest contract
```
Default tests parse all LookML and check join references and SQL snapshots.
`semantic.queries()` derives the checked-in contract SQL from selected
dimensions, measures and joins, plus the exact PDT SQL. This is a small
deterministic snapshot renderer, not a substitute for Looker's SQL compiler.
After editing LookML, regenerate snapshots from this function and review them.
No Looker instance or warehouse is required for tests.

Contracts default to `WAREHOUSE_CONTRACT_TARGET=teradata-emulator` and replay
synthetic recorded Teradata results, checking counts, decimal sums and keys.
`TD_EMULATOR_URL` selects an explicit unsupported endpoint stub.
`WAREHOUSE_CONTRACT_TARGET=snowflake` reads SNOWFLAKE_ACCOUNT, USER, ROLE,
WAREHOUSE, PRIVATE_KEY (each prefixed SNOWFLAKE_); absent credentials skip.
Configured Snowflake execution remains an explicit placeholder targeting
SFX_D1110_AFTER.COMPAT with QUERY_TAG
`{"run":"sfx-d1110","act":"consumers","consumer":"bi-semantic"}`.
No live Teradata, Looker compilation or Snowflake execution is asserted.
