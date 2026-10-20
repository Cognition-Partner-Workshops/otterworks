# Golden baseline (Oracle, 2025 month-end scenario)

Pinned output of the legacy warehouse that the dbt-postgres port is measured
against. Generated, never hand-edited:

```bash
make insurance-up NS=<ns>          # fresh fixture
make insurance-scenario NS=<ns>    # ledger 2025-01..2025-12, ETL, MV refresh
make insurance-golden NS=<ns>      # spools these CSVs via sqlplus in the container
make insurance-down NS=<ns>
make insurance-golden-check NS=<ns>  # fresh fixture -> scenario -> export -> diff -r, then tears down
```

| File | Source | Rows | Order |
|---|---|---|---|
| `agents.csv` | `COMMISSION_PAY.AGENTS` | 4 | agent_code |
| `products.csv` | `COMMISSION_PAY.PRODUCTS` | 4 | product_code |
| `policies.csv` | `COMMISSION_PAY.POLICIES` | 7 | policy_no |
| `commission_ledger.csv` | `COMMISSION_PAY.COMMISSION_LEDGER` | 115 | policy_id, agent_id, period_month |
| `fact_commission.csv` | `COMMISSION_DW.FACT_COMMISSION` joined to `DIM_AGENT`, `DIM_PRODUCT`, `DIM_PERIOD` | 115 | policy_id, agent_code, period_month |
| `mv_agent_commission_summary.csv` | `COMMISSION_DW.MV_AGENT_COMMISSION_SUMMARY` | 107 | agent_code, period_month, line_of_business |

Ledger and fact `commission_amt` both total 2328.31; MV `total_commission` totals 2328.31.

Format: header row, text double-quoted, dates `YYYY-MM-DD`, money and percentages
at scale 2 (`12.30`). Oracle identity keys that are not natural keys
(`ledger_id`, `rate_id`, `fact_id`, the dimension `*_key` columns) and load
timestamps (`calculated_at`, `loaded_at`) are not exported, so regeneration is
byte-identical across fresh fixtures. The export script is
`db/olap/golden/export_golden.sql`.
