# Finance analysis notebook

Separate repository owned by **@otterworks/data-science**. Run
finance_analysis.ipynb from this directory for month-end analysis, as
nb_dsci_pkhan (the DBQL account), against TDPROD / SFX_BILLING.
Connection settings are planted fake plaintext values in the notebook and
finance_nb/teradata.toml. Outputs remain cleared. FINANCE_WAREHOUSE_ENABLED defaults
true; setting false blocks connection creation. The helper lazily loads
teradatasql, accepts injected connectors, closes cursors and sanitizes errors.
The final notebook cell closes its connection.

## Analysis and sources
All warehouse-query tagged cells contain literal inline Teradata SQL:
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

The notebook keeps SEL, TOP 10, ZEROIFNULL, NULLIFZERO, ADD_MONTHS, LAST_DAY,
CURRENT_DATE - 90, 1200101 and FORMAT casts. Historical invoices start in 2020.
No FX conversion or credit-note allocation is performed. Currency aggregates are
not a currency-normalized financial statement. All-time payments offset the
overdue list; the DSO trend instead uses historical cutoffs.

## Checks and contracts
```sh
pip install -r requirements-dev.txt
python -m pytest
WAREHOUSE_CONTRACT_TARGET=replay python -m pytest contract
```

Unit tests validate nbformat, cleared outputs, query extraction and helper
normal/empty/error paths without executing the notebook or opening a warehouse.
Contracts extract the tagged SQL via AST and execute all four exact statements.
The default teradata-emulator target runs LIVE through ../contract-kit; follow its
README for Python bridge dependencies, TD_PG_PORT and CONTRACT_KIT_PYTHON.
Seed with ROWS_PER_TABLE=800 and BUSINESS_DATE=20261109. Runtime defaults to the
repository root; TD_EMULATOR_HOME overrides it.
CONTRACT_RECORD=true python -m pytest contract re-records live JSON; review
expected counts, keys and sums after changes. Replay needs neither a warehouse
nor bridge dependencies and runs in a dedicated CI job.
snowflake-semantics uses the shared live bridge. snowflake is an explicit
placeholder: missing SNOWFLAKE_ACCOUNT, USER, ROLE, WAREHOUSE or PRIVATE_KEY skips;
configured execution is unsupported. Metadata: SFX_D1110_AFTER.COMPAT, query tag
`{"run":"sfx-d1110","act":"consumers","consumer":"finance-notebook"}`.

## Databricks cutover (run dbx-d1111)
`FINANCE_WAREHOUSE` selects the notebook read path: `teradata` (default, unchanged),
`teradata-emulator` (old path: the literal Teradata SQL through ../contract-kit/bridge.py)
or `databricks` (native rewrites in finance_nb/databricks_queries.py through
finance_nb/databricks_warehouse.py; catalog cpw, schema dbx_d1111_after, every statement
tagged `/* run=dbx-d1111 act=consumers step=... consumer=finance-notebook */`).
`FINANCE_AS_OF=YYYY-MM-DD` pins CURRENT_DATE on both paths; contracts pin 2026-11-09
(BUSINESS_DATE 20261109) via `CONTRACT_AS_OF`, defaulting to it for the live target.

Decision: native Databricks rewrite, no compatibility view. Every Teradata construct here is
query syntax (SEL, TOP, ZEROIFNULL/NULLIFZERO, FORMAT casts, ADD_MONTHS, integer date
1200101, DATE +/- n), which a view cannot absorb; the columns read are ids, dates,
DECIMAL(14,2) amounts and VARCHAR CASESPECIFIC account fields, so there is no CHAR padding or
NOT CASESPECIFIC comparison to emulate; month labels are exactly 7 characters. The notebook is
ad hoc / month-end and the only reader of these query shapes, while billing__* targets are
shared, so nothing is added to dbx_d1111_after. DSO keeps the old path's division precision
(16 significant digits, as the emulator's DECIMAL division); default Databricks DECIMAL
division keeps only 6 decimals and broke the contract on the first live run.

Old path inputs must equal cpw.dbx_d1111_before: seed with ROWS_PER_TABLE=2000 (INVOICE_HDR
2100, PAYMENT 2000, CUSTOMER_ACCOUNT 300); the 800-row fixture behind contract/expected does
not match the live baseline. contract/recorded/live-baseline holds the old path's output on
that data (`CONTRACT_AS_OF=2026-11-09 python -m contract.record_baseline`).

```sh
WAREHOUSE_CONTRACT_TARGET=databricks python -m pytest contract   # skips without DATABRICKS_HOST/TOKEN/WAREHOUSE_ID
```
The live target checks row counts and keys against contract/expected and every value
(including the expected sum columns) against the old read path on the same data.
