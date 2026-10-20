# Rate audit retention (rule RA-1)

| | |
|---|---|
| Store | `audit_row_change` rows for `COMMISSION_RATES`; `rate_audit_log` rows with action `RATE_UPSERT` / `RATE_END` |
| Period | `p_retention_years`, default **7**, minimum 7 (lower is refused, ORA-20910) |
| Clock starts | the **later** of the rate's `effective_to` and the last day of the last `commission_ledger.period_month` that used the rate; for a rate deleted outright, the `DELETE` audit row |
| Never purged | while the rate is open (`effective_to IS NULL`), and no row until it is itself the full period old |
| Procedure | `rate_retention_pkg.purge(p_as_of, p_retention_years, p_dry_run DEFAULT TRUE)`, policy name `rate-audit-7y`, via `retention_kit.purge` |
| Clock per rate | `v_rate_retention` (`clock_start` is NULL while the rate is open) |
| Evidence | one `retention_run` row per table per call, dry or real |
| Test | `db/tests/run_retention_tests.sql` (R1–R5) |

The clock does not start at `logged_at` because the seeded rates 1–4 have
been open since 2024 and `commission_ledger` still pays on them: counting
from `logged_at` would delete the only record of who set a rate that is
still in use. 23 NYCRR 500.6(b) asks for at least five years on records that
rebuild financial transactions; seven years counted from the last payment
period stays above it.

`rate_audit_log` has no `rate_id`, so its rate rows are kept while **any**
rate in the same product/agent scope is still retained. `SPLIT_SET` and
`COMMISSION_CALC` rows are policy records, outside RA-1.

```sql
VARIABLE n NUMBER
EXEC :n := rate_retention_pkg.purge(p_as_of => TRUNC(SYSDATE));                      -- dry run
EXEC :n := rate_retention_pkg.purge(p_as_of => TRUNC(SYSDATE), p_dry_run => FALSE);  -- purge
SELECT * FROM retention_run ORDER BY run_id DESC;
```
