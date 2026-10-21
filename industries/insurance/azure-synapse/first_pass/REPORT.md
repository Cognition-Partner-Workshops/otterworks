# First-pass conversion report

Automated first pass over the claims warehouse, run against Snowflake with the frozen window loaded.

| Object | Type | First-pass output | Compile | Issue markers | Manual work |
|---|---|---|---|---|---|
| dw.usp_build_producer_scorecard | procedure | `snowflake/usp_build_producer_scorecard.sql` | fails | dynamic SQL rewritten to `EXECUTE IMMEDIATE`; cursor rewritten to `FOR`; `@@ROWCOUNT` mapped to `SQLROWCOUNT` at every use; `TOP 1` rewritten to `QUALIFY` | yes |
| dw.fn_holder_display_name | function | `snowflake/fn_holder_display_name.sql` | compiles | `CONCAT` carried over unchanged | review |
| dw.usp_refresh_claim_summary | procedure | `snowflake/usp_refresh_claim_summary.sql` | compiles | none | review |
| dw.usp_refresh_policy_contact | procedure | `snowflake/usp_refresh_policy_contact.sql` | compiles | `ISNULL` mapped to `COALESCE` | review |
| dw.v_claim_audit | view | `snowflake/v_claim_audit.sql` | compiles | `DATEPART(weekday, ...)` mapped to `DAYOFWEEK` | review |
| dw.v_policy_audit | view | `snowflake/v_policy_audit.sql` | compiles | `DATEPART(weekday, ...)` mapped to `DAYOFWEEK` | review |
| m_load_claim_feed | mapping | not converted | n/a | SQL overrides and connection left as exported | yes |
| m_load_premium_feed | mapping | not converted | n/a | SQL overrides and connection left as exported | yes |
| producer_dashboard.qvs | load script | not converted | n/a | `SQL SELECT` blocks left as exported | yes |

Tables: `snowflake/00_ddl.sql` (all tables compile and load).
