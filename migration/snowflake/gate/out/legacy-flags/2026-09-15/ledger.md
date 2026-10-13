Parity PASS=24 DIVERGE=1 PENDING=0

| Unit | Status | Rows (SQL Server / Snowflake) | Differing keys |
| --- | --- | ---: | ---: |
| load_dim_date | PASS | 3926 / 3926 | 0 |
| load_dim_tenant | PASS | 60 / 60 | 0 |
| load_dim_plan | PASS | 7 / 7 | 0 |
| load_dim_user | PASS | 2399 / 2399 | 0 |
| load_dim_workspace | PASS | 180 / 180 | 0 |
| load_dim_document | PASS | 39982 / 39982 | 0 |
| load_dim_file | PASS | 24993 / 24993 | 0 |
| rollup_storage_daily | PASS | 60 / 60 | 0 |
| rollup_usage_events | PASS | 7789 / 7789 | 0 |
| rollup_seats | PASS | 60 / 60 | 0 |
| rollup_collab_daily | PASS | 1529 / 1529 | 0 |
| rollup_audit | PASS | 5187 / 5187 | 0 |
| rollup_document_status | PASS | 360 / 360 | 0 |
| rollup_retention | PASS | 8388 / 8388 | 0 |
| build_invoice_lines | PASS | 184 / 184 | 0 |
| rate_overage | PASS | 60 / 60 | 0 |
| apply_plan_limits | PASS | 60 / 60 | 0 |
| build_capacity_forecast_input | PASS | 960 / 960 | 0 |
| build_mart_tenant_usage | PASS | 60 / 60 | 0 |
| build_mart_plan_seat_summary | PASS | 3 / 3 | 0 |
| build_mart_overage | PASS | 60 / 60 | 0 |
| build_mart_retention | PASS | 240 / 240 | 0 |
| build_mart_audit | PASS | 1928 / 1928 | 0 |
| log_run | PASS | 35 / 35 | 0 |
| purge_expired | DIVERGE | 82 / 35 | 35 |

### purge_expired

- `{"object_name": "pkg_analytics"}` `<duplicate key>`: SQL Server `3 rows`, Snowflake `1 rows`
- `{"object_name": "pkg_audit"}` `<duplicate key>`: SQL Server `3 rows`, Snowflake `1 rows`
- `{"object_name": "pkg_auth_memberships"}` `<duplicate key>`: SQL Server `3 rows`, Snowflake `1 rows`
- `{"object_name": "pkg_auth_users"}` `<duplicate key>`: SQL Server `3 rows`, Snowflake `1 rows`
- `{"object_name": "pkg_billing_core"}` `<duplicate key>`: SQL Server `3 rows`, Snowflake `1 rows`
- `{"object_name": "pkg_billing_invoices"}` `<duplicate key>`: SQL Server `3 rows`, Snowflake `1 rows`
- `{"object_name": "pkg_billing_usage"}` `<duplicate key>`: SQL Server `3 rows`, Snowflake `1 rows`
- `{"object_name": "pkg_collaboration"}` `<duplicate key>`: SQL Server `3 rows`, Snowflake `1 rows`
- `{"object_name": "pkg_document_versions"}` `<duplicate key>`: SQL Server `3 rows`, Snowflake `1 rows`
- `{"object_name": "pkg_documents"}` `<duplicate key>`: SQL Server `3 rows`, Snowflake `1 rows`
Explanation: Accepted; cannot match by construction. The manifest compares the whole ops.etl_run_log by object_name only (no business date), and the legacy log has one row per object per run (82 rows for 35 objects), so every key is a duplicate on the SQL Server side. OPS.PURGE_EXPIRED is the latest status per object inside the 400-day window; the deletes themselves run in task UBW_WEEKLY_RETENTION. All 35 objects are present on both sides with status succeeded.
