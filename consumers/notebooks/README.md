# Finance analysis notebook

Separate repository owned by **@otterworks/data-science**. Run
finance_analysis.ipynb from this directory for month-end analysis against
Snowflake SFX_D1110_AFTER.COMPAT. It no longer logs on to Teradata.
connect() reads SNOWFLAKE_ACCOUNT, USER, ROLE, WAREHOUSE and PRIVATE_KEY (PEM,
JWT key-pair auth); a missing setting fails before connecting. Every session sets
QUERY_TAG `{"run":"sfx-d1110","act":"consumers","consumer":"finance-notebook"}`
and TIMEZONE UTC. Outputs remain cleared. FINANCE_WAREHOUSE_ENABLED defaults
true; setting false blocks connection creation. The helper lazily loads
snowflake-connector-python, accepts injected connectors, closes cursors and
sanitizes errors. The final notebook cell closes its connection.

## Analysis and sources
All warehouse-query tagged cells contain literal inline Snowflake SQL over COMPAT views:
- Revenue: INVOICE_HDR (INVOICE_DT, TOTAL_AMOUNT, TAX_AMOUNT), trailing 12 months,
  including the current partial month; total less tax.
- DSO trend: monthly billed totals and cumulative open AR as of each month end.
  PAYMENT (INVOICE_ID, PAYMENT_DT, AMOUNT) is independently aggregated up to each
  month-end before joining invoices. DSO is month-end open AR / monthly billed * 30;
  no billing yields zero. Negative balances are retained.
- Collections versus billing: monthly totals over the last 90 days, full outer
  joined so either side may be absent. PAYMENT overlaps this account's DBQL report.
- Overdue accounts: INVOICE_HDR (INVOICE_ID, CUSTOMER_ID, INVOICE_DT, TOTAL_AMOUNT)
  joined to CUSTOMER_ACCOUNT (CUSTOMER_ID, ACCOUNT_NUMBER, ACCOUNT_NAME) and summed
  payments; top ten positive balances more than 30 days overdue.
  Due dates derive net-30 terms (INVOICE_DT + 30); the schema has no DUE_DT.

Teradata constructs were translated: SEL/TOP 10 -> SELECT/LIMIT 10, FORMAT casts
-> TO_CHAR/DATE, ZEROIFNULL/NULLIFZERO -> COALESCE/NULLIF, DATE +/- n -> DATEADD,
1200101 -> DATE '2020-01-01'. Overdue ties order by UPPER(ACCOUNT_NUMBER) to keep
the Teradata NOT CASESPECIFIC ordering. The pre-migration statements are frozen in
contract/teradata/*.sql for parity tooling only. Historical invoices start in 2020.
No FX conversion or credit-note allocation is performed. Currency aggregates are
not a currency-normalized financial statement. All-time payments offset the
overdue list; the DSO trend instead uses historical cutoffs.

## Checks and contracts
```sh
pip install -r requirements-dev.txt
python -m pytest
WAREHOUSE_CONTRACT_TARGET=replay python -m pytest contract
WAREHOUSE_CONTRACT_TARGET=snowflake python -m pytest contract -v -s
```

Unit tests validate nbformat, cleared outputs, query extraction, the absence of
Teradata SQL and logon settings, and helper normal/empty/error paths without
executing the notebook or opening a warehouse.

teradata-emulator, snowflake-semantics and replay run the frozen Teradata baseline
(contract/teradata/) through ../contract-kit and assert the recorded counts, keys
and sums. Live emulator runs force TD_USER=svc_exit_parity (the parity-tooling
account) and refuse any other TD_USER. Seed with ROWS_PER_TABLE=800 and
BUSINESS_DATE=20261109. CONTRACT_RECORD=true re-records live JSON.

snowflake runs the notebook's exact SQL against SFX_D1110_AFTER.COMPAT on
SFX_D1110_PARITY_WH (override with SNOWFLAKE_CONTRACT_WAREHOUSE), asserts the
session's database, schema, warehouse and QUERY_TAG, and prints each query ID.
Missing SNOWFLAKE_ACCOUNT, USER, ROLE or PRIVATE_KEY skips. It must agree with the
recorded Teradata fixtures on column names and order, row counts, month keys
(revenue, DSO, collections), zero/non-zero billed and collected months, and, for
overdue accounts present in both, name and oldest due date; overdue rows are the
reserved edge-case accounts with positive balances sorted descending.
Intended differences: amounts and sums are not compared because Snowflake holds
the full shared seed (200,000 invoices) while the fixtures were recorded on the
800-row emulator seed, and DSO precision follows Snowflake NUMBER division.
