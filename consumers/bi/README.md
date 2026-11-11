# bi-semantic

A separate repository owned by **@otterworks/bi**. The Looker connection
tdprod_fin uses the Teradata dialect, svc_bi_semantic and TDPROD / SFX_BILLING.
connection.md holds the planted fake plaintext settings and default-on access
attribute. The finance_four_hours datagroup refreshes PDTs every four hours.

## Model and columns
- invoices: INVOICE_HDR (INVOICE_ID, CUSTOMER_ID, INVOICE_NUMBER, INVOICE_DT,
  TOTAL_AMOUNT, TAX_AMOUNT). Logical accounts/customers both resolve to the real
  CUSTOMER_ACCOUNT entity (CUSTOMER_ID, ACCOUNT_NUMBER, ACCOUNT_NAME, CURRENCY_CD,
  REGION_CD); the two many-to-one joins retain their separate semantic roles.
- payments: PAYMENT (PAYMENT_ID, PAYMENT_DT, AMOUNT).
- gl_journal: GL_JOURNAL_LINE (JOURNAL_LINE_ID, GL_ACCOUNT_ID, POSTING_DT,
  DEBIT_AMOUNT, CREDIT_AMOUNT); joins GL_ACCOUNT (GL_ACCOUNT_ID, ACCOUNT_NAME,
  ACCOUNT_TYPE). Periods are derived from posting dates.
- invoice_revenue: V_INVOICE_REVENUE (INVOICE_PERIOD, CURRENCY_CD, INVOICE_COUNT,
  TOTAL_AMOUNT), overlapping this account's DBQL reports.
- overdue_accounts PDT: top 100 positive balances more than 30 days overdue,
  joining invoice headers, independently summed payments and customer accounts.
  Due dates use net-30 terms (INVOICE_DT + 30); the schema has no DUE_DT.

The existing logical field names remain stable. No FX conversion is performed;
aggregate views sum currencies together unless the caller selects currency.
Invoices include tax, payment offsets use all recorded payments.
SQL keeps SEL, TOP 100, ZEROIFNULL, FORMAT casts, integer date math, 1200101 and
QUALIFY ROW_NUMBER.

## Checks and contracts
```sh
pip install -r requirements-dev.txt
python -m pytest
WAREHOUSE_CONTRACT_TARGET=replay python -m pytest contract
```

Tests parse every LookML file, resolve joins, verify access/datagroup settings and
compare checked-in SQL snapshots to semantic.py's selected-field renderer.
This renderer is intentionally limited, not a replacement for Looker's compiler.
Looker compilation requires an external Looker installation.

The default teradata-emulator contract executes all five generated query
snapshots LIVE through ../contract-kit. Follow its README for bridge dependencies,
TD_PG_PORT and CONTRACT_KIT_PYTHON. Seed with ROWS_PER_TABLE=800 and
BUSINESS_DATE=20261109. Runtime defaults to the repository root; TD_EMULATOR_HOME
overrides it. CONTRACT_RECORD=true python -m pytest contract re-records exact live
JSON. Review expected counts, keys and monetary sums after changes. Replay needs
no bridge dependencies or warehouse and runs in a dedicated CI job.
snowflake-semantics invokes the shared live bridge. snowflake is an explicit
placeholder: missing SNOWFLAKE_ACCOUNT, USER, ROLE, WAREHOUSE or PRIVATE_KEY skips;
configured execution is unsupported. Metadata: SFX_D1110_AFTER.COMPAT, query tag
`{"run":"sfx-d1110","act":"consumers","consumer":"bi-semantic"}`.

## Databricks target (run dbx-d1111)
`databricks/` holds the Databricks-dialect model (connection `dbx_fin`, catalog `cpw`,
schema `dbx_d1111_after`). It mirrors `finance.model.lkml` explore-for-explore; only the
SQL dialect and table names change (native rewrite, no compatibility views). Snapshots
live in `contract/queries/databricks/` and are checked by `python -m pytest`.

```sh
pip install -r requirements-dev.txt -r ../contract-kit/requirements-databricks.txt
# old read path: emulator seeded to match the live baseline
make -C ../.. sfx-teradata-up NS=dbx-d1111-consumers-bi-semantic ROWS_PER_TABLE=2000 BUSINESS_DATE=20261109
export TD_PG_PORT=55203
python -m contract.input_equality      # emulator inputs == cpw.dbx_d1111_before (count + hash)
python -m contract.old_path            # records recorded/teradata-baseline + expected/baseline
# new read path (needs DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_WAREHOUSE_ID)
WAREHOUSE_CONTRACT_TARGET=databricks python -m pytest contract -v
```
Without the Databricks variables the `databricks` target skips with a clear reason.
`CURRENT_DATE` / `current_date()` is pinned to `CONTRACT_AS_OF_DATE` (default 2026-11-09,
the seeded business date) on both paths. The `databricks` target asserts the team contract
(row count, sums, ordered keys) against `expected/baseline/` and exact row equality with the
old path in `recorded/teradata-baseline/`. `expected/` and `recorded/teradata/` stay the
800-row emulator/replay contract.

Cutover status is **red**: successful DBQL reads of `SFX_USERS.V_TEAM_MEMBERS`
are outside the five billing queries and have no complete after target. See
[shared_changes_needed.md](shared_changes_needed.md). The live contract includes
an explicit users dependency check; billing parity alone cannot certify cutover.
