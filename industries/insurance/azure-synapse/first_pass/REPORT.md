# First-pass conversion report

Automated first pass over the claims warehouse, run against Snowflake with the frozen window loaded.

| Object | Type | First-pass output | Compile | Issue markers | Manual work |
|---|---|---|---|---|---|
| dw.usp_build_producer_scorecard | procedure | `snowflake/usp_build_producer_scorecard.sql` | fails | 7 (1 FP-ERR, 6 FP-WARN): table options, dynamic SQL, cursor loop, `@@ROWCOUNT` (3), `TOP 1` | yes |
| dw.fn_holder_display_name | function | `snowflake/fn_holder_display_name.sql` | compiles | 1 FP-INFO: `CONCAT` carried over | review |
| dw.usp_refresh_claim_summary | procedure | `snowflake/usp_refresh_claim_summary.sql` | compiles | 0 | review |
| dw.usp_refresh_policy_contact | procedure | `snowflake/usp_refresh_policy_contact.sql` | compiles | 1 FP-INFO: `ISNULL` mapped to `COALESCE` | review |
| dw.v_claim_audit | view | `snowflake/v_claim_audit.sql` | compiles | 2 FP-WARN: `DATEPART(weekday, ...)` mapped to `DAYOFWEEK` | review |
| dw.v_policy_audit | view | `snowflake/v_policy_audit.sql` | compiles | 2 FP-WARN: `DATEPART(weekday, ...)` mapped to `DAYOFWEEK` | review |
| m_load_claim_feed | mapping | not converted | n/a | SQL overrides and connection left as exported | yes |
| m_load_premium_feed | mapping | not converted | n/a | SQL overrides and connection left as exported | yes |
| producer_dashboard.qvs | load script | not converted | n/a | `SQL SELECT` blocks left as exported | yes |

Tables: `snowflake/00_ddl.sql` (all tables compile and load).

Markers are `--` comments the converter writes above the line it changed: FP-ERR blocks compilation, FP-WARN needs review, FP-INFO is a straight mapping.
