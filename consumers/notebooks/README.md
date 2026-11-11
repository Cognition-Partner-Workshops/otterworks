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
