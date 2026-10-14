Report parity PASS=14 DIVERGE=16 PENDING=0

| Report | Status | Rows (SQL Server / Snowflake) | Differing keys | Parameters |
| --- | --- | ---: | ---: | --- |
| rpt_archived_content | PASS | 0 / 0 | 0 | @BusinessDate=2026-09-15 |
| rpt_audit_rollup | PASS | 1928 / 1928 | 0 | @BusinessDate=2026-09-15 |
| rpt_audit_sensitive_actions | PASS | 0 / 0 | 0 | @BusinessDate=2026-09-15 |
| rpt_audit_user_activity | PASS | 5187 / 5187 | 0 | @BusinessDate=2026-09-15 |
| rpt_capacity_forecast | DIVERGE | 960 / 926 | 934 | @BusinessDate=2026-09-15 |
| rpt_document_status | DIVERGE | 360 / 540 | 360 | @BusinessDate=2026-09-15 |
| rpt_invoice_lines | PASS | 184 / 184 | 0 | @BusinessDate=2026-09-15 |
| rpt_invoice_totals_by_tenant | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-15 |
| rpt_monthly_billing_summary | PASS | 8 / 8 | 0 | @BusinessDate=2026-09-15 |
| rpt_overage_by_tier | DIVERGE | 3 / 3 | 3 | @BusinessDate=2026-09-15 |
| rpt_overage_charges | DIVERGE | 60 / 60 | 58 | @BusinessDate=2026-09-15 |
| rpt_plan_mix | DIVERGE | 3 / 3 | 3 | @BusinessDate=2026-09-15 |
| rpt_plan_tier_summary | DIVERGE | 1 / 1 | 1 | @BusinessDate=2026-09-15, @PlanTier=Growth |
| rpt_retention_candidates | PASS | 8388 / 8388 | 0 | @BusinessDate=2026-09-15 |
| rpt_retention_summary | PASS | 240 / 240 | 0 | @BusinessDate=2026-09-15 |
| rpt_seat_count_by_tenant | DIVERGE | 60 / 60 | 50 | @BusinessDate=2026-09-15 |
| rpt_seat_limit_headroom | DIVERGE | 60 / 60 | 50 | @BusinessDate=2026-09-15 |
| rpt_seat_utilization | DIVERGE | 60 / 60 | 50 | @BusinessDate=2026-09-15 |
| rpt_seats_over_limit | DIVERGE | 30 / 30 | 26 | @BusinessDate=2026-09-15 |
| rpt_storage_growth_trend | DIVERGE | 960 / 926 | 826 | @BusinessDate=2026-09-15 |
| rpt_storage_vs_included | DIVERGE | 60 / 60 | 58 | @BusinessDate=2026-09-15 |
| rpt_tenant_active_users | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-15 |
| rpt_tenant_api_units | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-15 |
| rpt_tenant_compute_units | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-15 |
| rpt_tenant_content_counts | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-15 |
| rpt_tenant_storage_peak | DIVERGE | 60 / 60 | 52 | @BusinessDate=2026-09-15 |
| rpt_tenant_usage_by_region | DIVERGE | 5 / 5 | 5 | @BusinessDate=2026-09-15 |
| rpt_tenant_usage_daily | DIVERGE | 60 / 60 | 52 | @BusinessDate=2026-09-15 |
| rpt_tenant_usage_top20 | DIVERGE | 20 / 20 | 19 | @BusinessDate=2026-09-15 |
| rpt_trash_purge_candidates | PASS | 2647 / 2647 | 0 | @BusinessDate=2026-09-15 |

### rpt_capacity_forecast

- `{"business_date": "2026-09-15", "observation_date": "2026-08-31", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `488193`, Snowflake `487476`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-01", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `492690`, Snowflake `488455`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-02", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-03", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-04", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `505723`, Snowflake `501432`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-05", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `510081`, Snowflake `509417`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-06", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `514319`, Snowflake `513574`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-07", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-08", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `523039`, Snowflake `522404`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-09", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `seat_count`: SQL Server `45`, Snowflake `40`
Explanation: Inherited from build_capacity_forecast_input (storage-day bucketing and seat_count). forecast_bytes_30d is computed by the Snowpark port with the legacy job's arithmetic and matches exactly when the inputs match (PASS with the legacy flags); forecast_generated_at is wall-clock and not compared. Data owners decide.

### rpt_document_status

- `{"business_date": "2026-09-15", "status_label": "active", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed", "workspace_id": "35edecc5-0a4d-423c-b77b-6c9c0faa7b4f"}` `document_count`: SQL Server `199`, Snowflake `193`
- `{"business_date": "2026-09-15", "status_label": "unknown", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed", "workspace_id": "35edecc5-0a4d-423c-b77b-6c9c0faa7b4f"}` `<missing in sqlserver>`: SQL Server `row missing`, Snowflake `row present`
- `{"business_date": "2026-09-15", "status_label": "active", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed", "workspace_id": "57ccf8c7-5d5c-42f8-89fb-66aaa9aeba73"}` `document_count`: SQL Server `170`, Snowflake `163`
- `{"business_date": "2026-09-15", "status_label": "unknown", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed", "workspace_id": "57ccf8c7-5d5c-42f8-89fb-66aaa9aeba73"}` `<missing in sqlserver>`: SQL Server `row missing`, Snowflake `row present`
- `{"business_date": "2026-09-15", "status_label": "active", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c", "workspace_id": "05c8bd1f-f285-47da-bacb-7723a2cdb84e"}` `document_count`: SQL Server `185`, Snowflake `176`
- `{"business_date": "2026-09-15", "status_label": "unknown", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c", "workspace_id": "05c8bd1f-f285-47da-bacb-7723a2cdb84e"}` `<missing in sqlserver>`: SQL Server `row missing`, Snowflake `row present`
- `{"business_date": "2026-09-15", "status_label": "active", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c", "workspace_id": "3e50283f-c8d1-49ab-a0e3-907e7626c3b9"}` `document_count`: SQL Server `173`, Snowflake `168`
- `{"business_date": "2026-09-15", "status_label": "unknown", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c", "workspace_id": "3e50283f-c8d1-49ab-a0e3-907e7626c3b9"}` `<missing in sqlserver>`: SQL Server `row missing`, Snowflake `row present`
- `{"business_date": "2026-09-15", "status_label": "active", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c", "workspace_id": "bdc1f5f3-e7ab-4ee3-9364-a079dd5762d8"}` `document_count`: SQL Server `180`, Snowflake `174`
- `{"business_date": "2026-09-15", "status_label": "unknown", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c", "workspace_id": "bdc1f5f3-e7ab-4ee3-9364-a079dd5762d8"}` `<missing in sqlserver>`: SQL Server `row missing`, Snowflake `row present`
Explanation: Inherited from rollup_document_status: documents with a NULL archived flag are 'unknown' in Snowflake instead of 'active' (1152 documents). Snowflake is right; PASS with legacy_null_archived_counted_active=true. Not invoiced.

### rpt_overage_by_tier

- `{"business_date": "2026-09-15", "plan_tier": "growth"}` `overage_gb`: SQL Server `876`, Snowflake `830.959`
- `{"business_date": "2026-09-15", "plan_tier": "scale"}` `overage_gb`: SQL Server `878`, Snowflake `792.863`
- `{"business_date": "2026-09-15", "plan_tier": "starter"}` `overage_gb`: SQL Server `275`, Snowflake `276.035`
Explanation: Inherited from rate_overage (whole-GB integer truncation, invoiced) and rollup_storage_daily (storage day): bytes_used, overage_gb and overage_cents differ, see the rate_overage ledger entry for totals. PASS with legacy_overage_whole_gb_truncation=true and legacy_storage_day_eastern_fixed_offset=true. Finance decides at cutover.

### rpt_overage_charges

- `{"business_date": "2026-09-15", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `bytes_used`: SQL Server `580506353664`, Snowflake `575829704704`
- `{"business_date": "2026-09-15", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c"}` `overage_gb`: SQL Server `3`, Snowflake `3.731`
- `{"business_date": "2026-09-15", "tenant_id": "040ef62f-cab7-4279-b317-8dbd18e12867"}` `overage_gb`: SQL Server `14`, Snowflake `14.733`
- `{"business_date": "2026-09-15", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `bytes_used`: SQL Server `555269226496`, Snowflake `547906125824`
- `{"business_date": "2026-09-15", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `overage_gb`: SQL Server `9`, Snowflake `9.991`
- `{"business_date": "2026-09-15", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `bytes_used`: SQL Server `64506298368`, Snowflake `63799558144`
- `{"business_date": "2026-09-15", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `bytes_used`: SQL Server `45624590336`, Snowflake `45104496640`
- `{"business_date": "2026-09-15", "tenant_id": "154b7a42-20b5-4d23-8a24-54dfbc579609"}` `bytes_used`: SQL Server `48463085568`, Snowflake `47444918272`
- `{"business_date": "2026-09-15", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `bytes_used`: SQL Server `4489175105536`, Snowflake `4477882990592`
- `{"business_date": "2026-09-15", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `bytes_used`: SQL Server `69049778176`, Snowflake `68059922432`
Explanation: Inherited from rate_overage (whole-GB integer truncation, invoiced) and rollup_storage_daily (storage day): bytes_used, overage_gb and overage_cents differ, see the rate_overage ledger entry for totals. PASS with legacy_overage_whole_gb_truncation=true and legacy_storage_day_eastern_fixed_offset=true. Finance decides at cutover.

### rpt_plan_mix

- `{"business_date": "2026-09-15", "plan_tier": "growth"}` `seat_count`: SQL Server `863`, Snowflake `789`
- `{"business_date": "2026-09-15", "plan_tier": "scale"}` `seat_count`: SQL Server `438`, Snowflake `393`
- `{"business_date": "2026-09-15", "plan_tier": "starter"}` `seat_count`: SQL Server `1307`, Snowflake `1181`
Explanation: Inherited from rollup_seats (users in two workspaces counted twice by the legacy procedure): seat_count and the columns derived from it differ (seat_limit and over_limit match). PASS with legacy_seats_count_workspace_memberships=true. Decided at cutover: the corrected count ships; the legacy count stays available to Billing behind the flag.

### rpt_plan_tier_summary

- `{"business_date": "2026-09-15", "plan_tier": "growth"}` `seat_count`: SQL Server `863`, Snowflake `789`
Explanation: Inherited from rollup_seats (users in two workspaces counted twice by the legacy procedure): seat_count and the columns derived from it differ (seat_limit and over_limit match). PASS with legacy_seats_count_workspace_memberships=true. Decided at cutover: the corrected count ships; the legacy count stays available to Billing behind the flag. The RDL passes @PlanTier='Growth' (title case) against lower-case data and relies on SQL Server's case-insensitive collation; the view's en-ci collation on plan_tier returns the same row in Snowflake (a case-sensitive comparison would return no rows).

### rpt_seat_count_by_tenant

- `{"business_date": "2026-09-15", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c"}` `seat_count`: SQL Server `44`, Snowflake `39`
- `{"business_date": "2026-09-15", "tenant_id": "040ef62f-cab7-4279-b317-8dbd18e12867"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `seat_count`: SQL Server `43`, Snowflake `39`
- `{"business_date": "2026-09-15", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `seat_count`: SQL Server `44`, Snowflake `39`
- `{"business_date": "2026-09-15", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `seat_count`: SQL Server `44`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "173d79f8-8296-4103-9432-264b163ebec5"}` `seat_count`: SQL Server `45`, Snowflake `40`
Explanation: Inherited from rollup_seats (users in two workspaces counted twice by the legacy procedure): seat_count and the columns derived from it differ (seat_limit and over_limit match). PASS with legacy_seats_count_workspace_memberships=true. Decided at cutover: the corrected count ships; the legacy count stays available to Billing behind the flag.

### rpt_seat_limit_headroom

- `{"business_date": "2026-09-15", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c"}` `seat_count`: SQL Server `44`, Snowflake `39`
- `{"business_date": "2026-09-15", "tenant_id": "040ef62f-cab7-4279-b317-8dbd18e12867"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `seat_count`: SQL Server `43`, Snowflake `39`
- `{"business_date": "2026-09-15", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `seat_count`: SQL Server `44`, Snowflake `39`
- `{"business_date": "2026-09-15", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `seat_count`: SQL Server `44`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "173d79f8-8296-4103-9432-264b163ebec5"}` `seat_count`: SQL Server `45`, Snowflake `40`
Explanation: Inherited from rollup_seats (users in two workspaces counted twice by the legacy procedure): seat_count and the columns derived from it differ (seat_limit and over_limit match). PASS with legacy_seats_count_workspace_memberships=true. Decided at cutover: the corrected count ships; the legacy count stays available to Billing behind the flag.

### rpt_seat_utilization

- `{"business_date": "2026-09-15", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c"}` `seat_count`: SQL Server `44`, Snowflake `39`
- `{"business_date": "2026-09-15", "tenant_id": "040ef62f-cab7-4279-b317-8dbd18e12867"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `seat_count`: SQL Server `43`, Snowflake `39`
- `{"business_date": "2026-09-15", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `seat_count`: SQL Server `44`, Snowflake `39`
- `{"business_date": "2026-09-15", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `seat_count`: SQL Server `44`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "173d79f8-8296-4103-9432-264b163ebec5"}` `seat_count`: SQL Server `45`, Snowflake `40`
Explanation: Inherited from rollup_seats (users in two workspaces counted twice by the legacy procedure): seat_count and the columns derived from it differ (seat_limit and over_limit match). PASS with legacy_seats_count_workspace_memberships=true. Decided at cutover: the corrected count ships; the legacy count stays available to Billing behind the flag.

### rpt_seats_over_limit

- `{"business_date": "2026-09-15", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c"}` `seat_count`: SQL Server `44`, Snowflake `39`
- `{"business_date": "2026-09-15", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `seat_count`: SQL Server `44`, Snowflake `39`
- `{"business_date": "2026-09-15", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `seat_count`: SQL Server `44`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "173d79f8-8296-4103-9432-264b163ebec5"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "1b3e1a63-0f8f-4b5a-8a27-61ded31636fe"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "1d573d09-6ffc-401a-90d6-c424a7e95989"}` `seat_count`: SQL Server `44`, Snowflake `39`
- `{"business_date": "2026-09-15", "tenant_id": "27557aaa-8749-43a8-91bc-1acd523bc5e0"}` `seat_count`: SQL Server `44`, Snowflake `40`
- `{"business_date": "2026-09-15", "tenant_id": "2b217fd0-6983-42aa-a5a9-14dbde5391fb"}` `seat_count`: SQL Server `44`, Snowflake `39`
Explanation: Inherited from rollup_seats (users in two workspaces counted twice by the legacy procedure): seat_count and the columns derived from it differ (seat_limit and over_limit match). PASS with legacy_seats_count_workspace_memberships=true. Decided at cutover: the corrected count ships; the legacy count stays available to Billing behind the flag.

### rpt_storage_growth_trend

- `{"business_date": "2026-09-15", "observation_date": "2026-08-31", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `488193`, Snowflake `487476`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-01", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `492690`, Snowflake `488455`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-04", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `505723`, Snowflake `501432`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-05", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `510081`, Snowflake `509417`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-06", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `514319`, Snowflake `513574`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-08", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `523039`, Snowflake `522404`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-10", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `531364`, Snowflake `530887`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-11", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `536015`, Snowflake `531987`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-12", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `540486`, Snowflake `536339`
- `{"business_date": "2026-09-15", "observation_date": "2026-09-14", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `548453`, Snowflake `545038`
Explanation: Inherited from build_capacity_forecast_input (storage-day bucketing, 28-day window). Inherited from rollup_storage_daily (UTC day vs the legacy fixed -4h Eastern bucketing): only storage_peak_mb / bytes_used differ (and sums built from them). Snowflake is right; PASS with legacy_storage_day_eastern_fixed_offset=true (gate/out/legacy-flags/). Data owners decide.

### rpt_storage_vs_included

- `{"business_date": "2026-09-15", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `bytes_used`: SQL Server `580506353664`, Snowflake `575829704704`
- `{"business_date": "2026-09-15", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c"}` `overage_gb`: SQL Server `3`, Snowflake `3.731`
- `{"business_date": "2026-09-15", "tenant_id": "040ef62f-cab7-4279-b317-8dbd18e12867"}` `overage_gb`: SQL Server `14`, Snowflake `14.733`
- `{"business_date": "2026-09-15", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `bytes_used`: SQL Server `555269226496`, Snowflake `547906125824`
- `{"business_date": "2026-09-15", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `overage_gb`: SQL Server `9`, Snowflake `9.991`
- `{"business_date": "2026-09-15", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `bytes_used`: SQL Server `64506298368`, Snowflake `63799558144`
- `{"business_date": "2026-09-15", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `bytes_used`: SQL Server `45624590336`, Snowflake `45104496640`
- `{"business_date": "2026-09-15", "tenant_id": "154b7a42-20b5-4d23-8a24-54dfbc579609"}` `bytes_used`: SQL Server `48463085568`, Snowflake `47444918272`
- `{"business_date": "2026-09-15", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `bytes_used`: SQL Server `4489175105536`, Snowflake `4477882990592`
- `{"business_date": "2026-09-15", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `bytes_used`: SQL Server `69049778176`, Snowflake `68059922432`
Explanation: Inherited from rate_overage (whole-GB integer truncation, invoiced) and rollup_storage_daily (storage day): bytes_used, overage_gb and overage_cents differ, see the rate_overage ledger entry for totals. PASS with legacy_overage_whole_gb_truncation=true and legacy_storage_day_eastern_fixed_offset=true. Finance decides at cutover.

### rpt_tenant_storage_peak

- `{"business_date": "2026-09-15", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `storage_peak_mb`: SQL Server `553614`, Snowflake `549154`
- `{"business_date": "2026-09-15", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `storage_peak_mb`: SQL Server `529546`, Snowflake `522524`
- `{"business_date": "2026-09-15", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `storage_peak_mb`: SQL Server `61518`, Snowflake `60844`
- `{"business_date": "2026-09-15", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `storage_peak_mb`: SQL Server `43511`, Snowflake `43015`
- `{"business_date": "2026-09-15", "tenant_id": "154b7a42-20b5-4d23-8a24-54dfbc579609"}` `storage_peak_mb`: SQL Server `46218`, Snowflake `45247`
- `{"business_date": "2026-09-15", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `storage_peak_mb`: SQL Server `4281211`, Snowflake `4270442`
- `{"business_date": "2026-09-15", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `storage_peak_mb`: SQL Server `65851`, Snowflake `64907`
- `{"business_date": "2026-09-15", "tenant_id": "173d79f8-8296-4103-9432-264b163ebec5"}` `storage_peak_mb`: SQL Server `55510`, Snowflake `54415`
- `{"business_date": "2026-09-15", "tenant_id": "193215f9-31d2-47cd-a689-7d5bc17a11eb"}` `storage_peak_mb`: SQL Server `3931849`, Snowflake `3931374`
- `{"business_date": "2026-09-15", "tenant_id": "1b3e1a63-0f8f-4b5a-8a27-61ded31636fe"}` `storage_peak_mb`: SQL Server `42480`, Snowflake `42303`
Explanation: Inherited from rollup_storage_daily (UTC day vs the legacy fixed -4h Eastern bucketing): only storage_peak_mb / bytes_used differ (and sums built from them). Snowflake is right; PASS with legacy_storage_day_eastern_fixed_offset=true (gate/out/legacy-flags/). Data owners decide.

### rpt_tenant_usage_by_region

- `{"business_date": "2026-09-15", "region_code": "ap-southeast-2"}` `bytes_used`: SQL Server `10885583077376`, Snowflake `10826980261888`
- `{"business_date": "2026-09-15", "region_code": "eu-central-1"}` `bytes_used`: SQL Server `12280269897728`, Snowflake `12258050572288`
- `{"business_date": "2026-09-15", "region_code": "eu-west-1"}` `bytes_used`: SQL Server `12610031321088`, Snowflake `12554864689152`
- `{"business_date": "2026-09-15", "region_code": "us-east-1"}` `bytes_used`: SQL Server `12432750673920`, Snowflake `12368779149312`
- `{"business_date": "2026-09-15", "region_code": "us-west-2"}` `bytes_used`: SQL Server `12201140158464`, Snowflake `12135301120000`
Explanation: Inherited from rollup_storage_daily (UTC day vs the legacy fixed -4h Eastern bucketing): only storage_peak_mb / bytes_used differ (and sums built from them). Snowflake is right; PASS with legacy_storage_day_eastern_fixed_offset=true (gate/out/legacy-flags/). Data owners decide.

### rpt_tenant_usage_daily

- `{"business_date": "2026-09-15", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `storage_peak_mb`: SQL Server `553614`, Snowflake `549154`
- `{"business_date": "2026-09-15", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `storage_peak_mb`: SQL Server `529546`, Snowflake `522524`
- `{"business_date": "2026-09-15", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `storage_peak_mb`: SQL Server `61518`, Snowflake `60844`
- `{"business_date": "2026-09-15", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `storage_peak_mb`: SQL Server `43511`, Snowflake `43015`
- `{"business_date": "2026-09-15", "tenant_id": "154b7a42-20b5-4d23-8a24-54dfbc579609"}` `storage_peak_mb`: SQL Server `46218`, Snowflake `45247`
- `{"business_date": "2026-09-15", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `storage_peak_mb`: SQL Server `4281211`, Snowflake `4270442`
- `{"business_date": "2026-09-15", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `storage_peak_mb`: SQL Server `65851`, Snowflake `64907`
- `{"business_date": "2026-09-15", "tenant_id": "173d79f8-8296-4103-9432-264b163ebec5"}` `storage_peak_mb`: SQL Server `55510`, Snowflake `54415`
- `{"business_date": "2026-09-15", "tenant_id": "193215f9-31d2-47cd-a689-7d5bc17a11eb"}` `storage_peak_mb`: SQL Server `3931849`, Snowflake `3931374`
- `{"business_date": "2026-09-15", "tenant_id": "1b3e1a63-0f8f-4b5a-8a27-61ded31636fe"}` `storage_peak_mb`: SQL Server `42480`, Snowflake `42303`
Explanation: Inherited from rollup_storage_daily (UTC day vs the legacy fixed -4h Eastern bucketing): only storage_peak_mb / bytes_used differ (and sums built from them). Snowflake is right; PASS with legacy_storage_day_eastern_fixed_offset=true (gate/out/legacy-flags/). Data owners decide.

### rpt_tenant_usage_top20

- `{"business_date": "2026-09-15", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `storage_peak_mb`: SQL Server `4281211`, Snowflake `4270442`
- `{"business_date": "2026-09-15", "tenant_id": "193215f9-31d2-47cd-a689-7d5bc17a11eb"}` `storage_peak_mb`: SQL Server `3931849`, Snowflake `3931374`
- `{"business_date": "2026-09-15", "tenant_id": "212c0db7-dc12-4bb6-97fe-50a5096e8609"}` `storage_peak_mb`: SQL Server `3884023`, Snowflake `3845098`
- `{"business_date": "2026-09-15", "tenant_id": "25fea9ca-72dc-42d8-b6fb-3e7be292a1a0"}` `storage_peak_mb`: SQL Server `571678`, Snowflake `563524`
- `{"business_date": "2026-09-15", "tenant_id": "2a1db1ee-db91-47c2-9233-55190701e838"}` `storage_peak_mb`: SQL Server `605347`, Snowflake `602611`
- `{"business_date": "2026-09-15", "tenant_id": "32ee9387-ea76-4ab8-821c-a6097f34fb88"}` `storage_peak_mb`: SQL Server `571066`, Snowflake `570868`
- `{"business_date": "2026-09-15", "tenant_id": "38e979c2-2709-43ef-bf24-b824f410b873"}` `storage_peak_mb`: SQL Server `587525`, Snowflake `582730`
- `{"business_date": "2026-09-15", "tenant_id": "43cbcefc-2429-402a-bb14-9b50fb30468f"}` `storage_peak_mb`: SQL Server `573776`, Snowflake `567883`
- `{"business_date": "2026-09-15", "tenant_id": "4f7a5149-97af-4b8f-8cca-49809ddaf212"}` `storage_peak_mb`: SQL Server `614926`, Snowflake `611301`
- `{"business_date": "2026-09-15", "tenant_id": "6ec1190c-e799-4d58-9942-ccb5ad8f805a"}` `storage_peak_mb`: SQL Server `3920265`, Snowflake `3908827`
Explanation: Inherited from rollup_storage_daily (UTC day vs the legacy fixed -4h Eastern bucketing): only storage_peak_mb / bytes_used differ (and sums built from them). Snowflake is right; PASS with legacy_storage_day_eastern_fixed_offset=true (gate/out/legacy-flags/). Data owners decide. The top-20 set and order follow bytes_used.
