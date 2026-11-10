# bi-semantic

The production Looker read path is finance.model.lkml and views/*.lkml using
the Snowflake connection `sfx_fin` documented in connection.md. Logical field
names, default-on access grants and the four-hour PDT datagroup remain stable.
All sources are fully qualified in SFX_D1110_AFTER:
- COMPAT.INVOICE, ACCOUNT, PAYMENT and GL_JOURNAL_LINE provide the billing facts.
- RAW_BILLING.CUSTOMER_ACCOUNT supplies customer names/regions and
  RAW_BILLING.GL_ACCOUNT supplies account names/types absent from COMPAT.
- invoice_revenue derives currency/month aggregates from invoices joined to accounts.
- overdue_accounts computes positive net-30 balances, offset by all payments,
  restricted to the top 100 by balance descending then account number.

No FX conversion is performed; invoices include tax. Configure a platform-owned
writable PDT scratch schema separately from the read-only source schemas.

## Checks and contracts

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
WAREHOUSE_CONTRACT_TARGET=replay python -m pytest contract -q
WAREHOUSE_CONTRACT_TARGET=snowflake python -m pytest contract -v -s
```

Tests parse LookML, resolve joins, verify access/datagroup settings and compare
Snowflake snapshots with semantic.py. The selected-field renderer is deliberately
limited; full Looker compilation requires an external Looker installation.

contract/queries/*.sql are regenerated Snowflake queries.
contract/queries/teradata/*.sql are unchanged frozen baseline queries used by
replay, teradata-emulator and snowflake-semantics. Replay requires no credentials.
Both emulator targets require TD_USER=svc_exit_parity; the retired
svc_bi_semantic account is explicitly rejected. Follow ../contract-kit/README.md
for bridge dependencies, TD_PG_PORT and CONTRACT_KIT_PYTHON. Use an 800-row seed
and BUSINESS_DATE=20261109. TD_EMULATOR_HOME overrides the repo runtime root.
CONTRACT_RECORD=true records emulator results; recorded/expected fixtures must
not be refreshed for the Snowflake migration.

The snowflake target uses JWT key-pair credentials from SNOWFLAKE_ACCOUNT,
SNOWFLAKE_USER, SNOWFLAKE_ROLE and SNOWFLAKE_PRIVATE_KEY (PEM), skipping if any
are absent. It always uses SFX_D1110_AFTER and SFX_D1110_PARITY_WH, UTC and the
exact query tag in connection.md, ignoring SNOWFLAKE_WAREHOUSE.
It prints each query ID without writing query-ID artifacts or creating objects.

Intended differences: the Snowflake dataset is about 250x the 800-row emulator
seed. Counts/sums for 2026-11, GL periods and the overdue account set differ.
CURRENT_DATE uses Snowflake's UTC date, not the emulator business date.
The live contract therefore checks label parity, invoice/revenue agreement,
zero GL movements, valid ordered positive overdue balances and case-safe
account numbers instead of exact seed totals. See contract/README.md.
