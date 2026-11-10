# finance-notebook
A separate repository owned by **@otterworks/data-science**. Ad hoc/month-end
analysis against TDPROD / FIN_DW as `nb_finance_analysis`.

## Run
Install requirements.txt in a Python 3.12 notebook kernel, open
finance_analysis.ipynb from this directory, and run cells in order.
The connection cell contains obviously fake credentials; replace them only in
your local environment. The helper also has a fake default connection config
in finance_nb/teradata.toml. It lazily imports teradatasql on connect, never
during import. Set FINANCE_WAREHOUSE_ENABLED=false to prevent connections
(default true). The caller owns and closes the connection in the final cell;
if a query fails, close it before rerunning. Query cursors close on all paths.
`run_query` accepts any connection implementing the cursor interface and
returns pandas dataframes without coercing warehouse decimals to floats.

Revenue is billed amount less tax over a trailing year (includes partial
months). DSO uses month-end outstanding invoice balances after payments up to
that month-end, divided by that month's billing times 30; no billed amount
returns zero. Credits offset AR; history starts 2020-01-01.
Collections vs billing covers the last 90 days, independently grouped by
payment/invoice date. Top ten accounts have positive balances overdue by
more than 30 days, after all recorded payments. There is no FX conversion;
inputs assume a single reporting currency.

Read columns:
- INVOICE: INVOICE_ID, ACCOUNT_ID, INVOICE_DT, DUE_DT, AMOUNT_DUE, TAX_AMT.
- PAYMENT: INVOICE_ID, PAYMENT_DT, AMOUNT.
- ACCOUNT: ACCOUNT_ID, CUSTOMER_ID, ACCOUNT_NO.
- CUSTOMER: CUSTOMER_ID, CUSTOMER_NAME.

## Checks
```sh
python -m pip install -r requirements-dev.txt
python -m pytest
python -m pytest contract
```
Outputs and execution counts are cleared in version control.
Tagged warehouse-query cells contain literal SQL extracted with Python AST,
without executing connection cells. Contracts receive those exact SQL strings.

Contracts default to WAREHOUSE_CONTRACT_TARGET=teradata-emulator and replay
synthetic recorded results; assertions check counts, monetary/DSO aggregates
and account/month keys against contract/expected.
TD_EMULATOR_URL selects an explicit unsupported endpoint stub.
WAREHOUSE_CONTRACT_TARGET=snowflake reads SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER,
SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE, SNOWFLAKE_PRIVATE_KEY; missing values skip.
Configured execution remains an explicit placeholder for SFX_D1110_AFTER.COMPAT,
with QUERY_TAG
`{"run":"sfx-d1110","act":"consumers","consumer":"finance-notebook"}`.
No live warehouse or notebook execution is asserted by replay tests.
