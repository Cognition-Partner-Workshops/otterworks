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
