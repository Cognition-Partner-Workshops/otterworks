Report parity PASS=29 DIVERGE=1 PENDING=0

| Report | Status | Rows (SQL Server / Snowflake) | Differing keys | Parameters |
| --- | --- | ---: | ---: | --- |
| rpt_archived_content | PASS | 0 / 0 | 0 | @BusinessDate=2026-09-15 |
| rpt_audit_rollup | PASS | 1928 / 1928 | 0 | @BusinessDate=2026-09-15 |
| rpt_audit_sensitive_actions | PASS | 0 / 0 | 0 | @BusinessDate=2026-09-15 |
| rpt_audit_user_activity | PASS | 5187 / 5187 | 0 | @BusinessDate=2026-09-15 |
| rpt_capacity_forecast | PASS | 960 / 960 | 0 | @BusinessDate=2026-09-15 |
| rpt_document_status | PASS | 360 / 360 | 0 | @BusinessDate=2026-09-15 |
| rpt_invoice_lines | PASS | 184 / 184 | 0 | @BusinessDate=2026-09-15 |
| rpt_invoice_totals_by_tenant | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-15 |
| rpt_monthly_billing_summary | PASS | 8 / 8 | 0 | @BusinessDate=2026-09-15 |
| rpt_overage_by_tier | PASS | 3 / 3 | 0 | @BusinessDate=2026-09-15 |
| rpt_overage_charges | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-15 |
| rpt_plan_mix | PASS | 3 / 3 | 0 | @BusinessDate=2026-09-15 |
| rpt_plan_tier_summary | PASS | 1 / 1 | 0 | @BusinessDate=2026-09-15, @PlanTier=Growth |
| rpt_retention_candidates | PASS | 8388 / 8388 | 0 | @BusinessDate=2026-09-15 |
| rpt_retention_summary | PASS | 240 / 240 | 0 | @BusinessDate=2026-09-15 |
| rpt_seat_count_by_tenant | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-15 |
| rpt_seat_limit_headroom | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-15 |
| rpt_seat_utilization | DIVERGE | 60 / 60 | 5 | @BusinessDate=2026-09-15 |
| rpt_seats_over_limit | PASS | 30 / 30 | 0 | @BusinessDate=2026-09-15 |
| rpt_storage_growth_trend | PASS | 960 / 960 | 0 | @BusinessDate=2026-09-15 |
| rpt_storage_vs_included | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-15 |
| rpt_tenant_active_users | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-15 |
| rpt_tenant_api_units | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-15 |
| rpt_tenant_compute_units | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-15 |
| rpt_tenant_content_counts | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-15 |
| rpt_tenant_storage_peak | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-15 |
| rpt_tenant_usage_by_region | PASS | 5 / 5 | 0 | @BusinessDate=2026-09-15 |
| rpt_tenant_usage_daily | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-15 |
| rpt_tenant_usage_top20 | PASS | 20 / 20 | 0 | @BusinessDate=2026-09-15 |
| rpt_trash_purge_candidates | PASS | 2647 / 2647 | 0 | @BusinessDate=2026-09-15 |

### rpt_seat_utilization

- `{"business_date": "2026-09-15", "tenant_id": "22ee38da-0421-4404-aa99-73730eff7c22"}` `utilization`: SQL Server `0.586666666666666`, Snowflake `0.586666666666667`
- `{"business_date": "2026-09-15", "tenant_id": "2a1db1ee-db91-47c2-9233-55190701e838"}` `utilization`: SQL Server `0.506666666666666`, Snowflake `0.506666666666667`
- `{"business_date": "2026-09-15", "tenant_id": "73449302-c55d-476e-8b44-f0b6aec751b5"}` `utilization`: SQL Server `0.586666666666666`, Snowflake `0.586666666666667`
- `{"business_date": "2026-09-15", "tenant_id": "d1b498dc-c111-47b2-b2e9-9d06f52f826c"}` `utilization`: SQL Server `0.586666666666666`, Snowflake `0.586666666666667`
- `{"business_date": "2026-09-15", "tenant_id": "d640e9cb-d19c-4a49-b699-92cd9b451e9e"}` `utilization`: SQL Server `0.506666666666666`, Snowflake `0.506666666666667`
Explanation: Fixed after this run: SQL Server truncates decimal(29,15) division at the 15th decimal, the view's cast rounded (0.586666666666666 vs ...667). The view now truncates; rpt_seat_utilization passes on both dates in the final runs.
