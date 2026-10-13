Report parity PASS=14 DIVERGE=16 PENDING=0

| Report | Status | Rows (SQL Server / Snowflake) | Differing keys | Parameters |
| --- | --- | ---: | ---: | --- |
| rpt_archived_content | PASS | 0 / 0 | 0 | @BusinessDate=2026-09-30 |
| rpt_audit_rollup | PASS | 1909 / 1909 | 0 | @BusinessDate=2026-09-30 |
| rpt_audit_sensitive_actions | PASS | 0 / 0 | 0 | @BusinessDate=2026-09-30 |
| rpt_audit_user_activity | PASS | 5024 / 5024 | 0 | @BusinessDate=2026-09-30 |
| rpt_capacity_forecast | DIVERGE | 1680 / 1680 | 1634 | @BusinessDate=2026-09-30 |
| rpt_document_status | DIVERGE | 360 / 540 | 360 | @BusinessDate=2026-09-30 |
| rpt_invoice_lines | PASS | 376 / 376 | 0 | @BusinessDate=2026-09-30 |
| rpt_invoice_totals_by_tenant | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-30 |
| rpt_monthly_billing_summary | PASS | 16 / 16 | 0 | @BusinessDate=2026-09-30 |
| rpt_overage_by_tier | DIVERGE | 3 / 3 | 3 | @BusinessDate=2026-09-30 |
| rpt_overage_charges | DIVERGE | 60 / 60 | 58 | @BusinessDate=2026-09-30 |
| rpt_plan_mix | DIVERGE | 3 / 3 | 3 | @BusinessDate=2026-09-30 |
| rpt_plan_tier_summary | DIVERGE | 1 / 1 | 1 | @BusinessDate=2026-09-30, @PlanTier=Growth |
| rpt_retention_candidates | PASS | 8448 / 8448 | 0 | @BusinessDate=2026-09-30 |
| rpt_retention_summary | PASS | 240 / 240 | 0 | @BusinessDate=2026-09-30 |
| rpt_seat_count_by_tenant | DIVERGE | 60 / 60 | 50 | @BusinessDate=2026-09-30 |
| rpt_seat_limit_headroom | DIVERGE | 60 / 60 | 50 | @BusinessDate=2026-09-30 |
| rpt_seat_utilization | DIVERGE | 60 / 60 | 50 | @BusinessDate=2026-09-30 |
| rpt_seats_over_limit | DIVERGE | 30 / 30 | 26 | @BusinessDate=2026-09-30 |
| rpt_storage_growth_trend | DIVERGE | 1680 / 1680 | 1439 | @BusinessDate=2026-09-30 |
| rpt_storage_vs_included | DIVERGE | 60 / 60 | 58 | @BusinessDate=2026-09-30 |
| rpt_tenant_active_users | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-30 |
| rpt_tenant_api_units | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-30 |
| rpt_tenant_compute_units | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-30 |
| rpt_tenant_content_counts | PASS | 60 / 60 | 0 | @BusinessDate=2026-09-30 |
| rpt_tenant_storage_peak | DIVERGE | 60 / 60 | 53 | @BusinessDate=2026-09-30 |
| rpt_tenant_usage_by_region | DIVERGE | 5 / 5 | 5 | @BusinessDate=2026-09-30 |
| rpt_tenant_usage_daily | DIVERGE | 60 / 60 | 53 | @BusinessDate=2026-09-30 |
| rpt_tenant_usage_top20 | DIVERGE | 20 / 20 | 17 | @BusinessDate=2026-09-30 |
| rpt_trash_purge_candidates | PASS | 2664 / 2664 | 0 | @BusinessDate=2026-09-30 |

### rpt_capacity_forecast

- `{"business_date": "2026-09-30", "observation_date": "2026-09-03", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-04", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `505723`, Snowflake `501432`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-05", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `510081`, Snowflake `509417`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-06", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `514319`, Snowflake `513574`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-07", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-08", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `523039`, Snowflake `522404`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-09", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-10", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `531364`, Snowflake `530887`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-11", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `536015`, Snowflake `531987`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-12", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `540486`, Snowflake `536339`
Explanation: Inherited from build_capacity_forecast_input (storage-day bucketing and seat_count). forecast_bytes_30d is computed by the Snowpark port with the legacy job's arithmetic and matches exactly when the inputs match (PASS with the legacy flags); forecast_generated_at is wall-clock and not compared. Data owners decide.

### rpt_document_status

- `{"business_date": "2026-09-30", "status_label": "active", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed", "workspace_id": "35edecc5-0a4d-423c-b77b-6c9c0faa7b4f"}` `document_count`: SQL Server `199`, Snowflake `193`
- `{"business_date": "2026-09-30", "status_label": "unknown", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed", "workspace_id": "35edecc5-0a4d-423c-b77b-6c9c0faa7b4f"}` `<missing in sqlserver>`: SQL Server `row missing`, Snowflake `row present`
- `{"business_date": "2026-09-30", "status_label": "active", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed", "workspace_id": "57ccf8c7-5d5c-42f8-89fb-66aaa9aeba73"}` `document_count`: SQL Server `170`, Snowflake `163`
- `{"business_date": "2026-09-30", "status_label": "unknown", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed", "workspace_id": "57ccf8c7-5d5c-42f8-89fb-66aaa9aeba73"}` `<missing in sqlserver>`: SQL Server `row missing`, Snowflake `row present`
- `{"business_date": "2026-09-30", "status_label": "active", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c", "workspace_id": "05c8bd1f-f285-47da-bacb-7723a2cdb84e"}` `document_count`: SQL Server `185`, Snowflake `176`
- `{"business_date": "2026-09-30", "status_label": "unknown", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c", "workspace_id": "05c8bd1f-f285-47da-bacb-7723a2cdb84e"}` `<missing in sqlserver>`: SQL Server `row missing`, Snowflake `row present`
- `{"business_date": "2026-09-30", "status_label": "active", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c", "workspace_id": "3e50283f-c8d1-49ab-a0e3-907e7626c3b9"}` `document_count`: SQL Server `174`, Snowflake `169`
- `{"business_date": "2026-09-30", "status_label": "unknown", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c", "workspace_id": "3e50283f-c8d1-49ab-a0e3-907e7626c3b9"}` `<missing in sqlserver>`: SQL Server `row missing`, Snowflake `row present`
- `{"business_date": "2026-09-30", "status_label": "active", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c", "workspace_id": "bdc1f5f3-e7ab-4ee3-9364-a079dd5762d8"}` `document_count`: SQL Server `182`, Snowflake `176`
- `{"business_date": "2026-09-30", "status_label": "unknown", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c", "workspace_id": "bdc1f5f3-e7ab-4ee3-9364-a079dd5762d8"}` `<missing in sqlserver>`: SQL Server `row missing`, Snowflake `row present`
Explanation: Inherited from rollup_document_status: documents with a NULL archived flag are 'unknown' in Snowflake instead of 'active' (1152 documents). Snowflake is right; PASS with legacy_null_archived_counted_active=true. Not invoiced.

### rpt_overage_by_tier

- `{"business_date": "2026-09-30", "plan_tier": "growth"}` `overage_gb`: SQL Server `2237`, Snowflake `2192.982`
- `{"business_date": "2026-09-30", "plan_tier": "scale"}` `overage_gb`: SQL Server `2185`, Snowflake `2132.984`
- `{"business_date": "2026-09-30", "plan_tier": "starter"}` `overage_gb`: SQL Server `580`, Snowflake `577.495`
Explanation: Inherited from rate_overage (whole-GB integer truncation, invoiced) and rollup_storage_daily (storage day): bytes_used, overage_gb and overage_cents differ, see the rate_overage ledger entry for totals. PASS with legacy_overage_whole_gb_truncation=true and legacy_storage_day_eastern_fixed_offset=true. Finance decides at cutover.

### rpt_overage_charges

- `{"business_date": "2026-09-30", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `bytes_used`: SQL Server `648854634496`, Snowflake `648407941120`
- `{"business_date": "2026-09-30", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c"}` `overage_gb`: SQL Server `12`, Snowflake `12.846`
- `{"business_date": "2026-09-30", "tenant_id": "040ef62f-cab7-4279-b317-8dbd18e12867"}` `bytes_used`: SQL Server `591485992960`, Snowflake `590797078528`
- `{"business_date": "2026-09-30", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `bytes_used`: SQL Server `667042185216`, Snowflake `659711590400`
- `{"business_date": "2026-09-30", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `bytes_used`: SQL Server `77593575424`, Snowflake `76855377920`
- `{"business_date": "2026-09-30", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `bytes_used`: SQL Server `75139907584`, Snowflake `74479304704`
- `{"business_date": "2026-09-30", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `bytes_used`: SQL Server `55986618368`, Snowflake `55716085760`
- `{"business_date": "2026-09-30", "tenant_id": "154b7a42-20b5-4d23-8a24-54dfbc579609"}` `bytes_used`: SQL Server `62520295424`, Snowflake `62063116288`
- `{"business_date": "2026-09-30", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `bytes_used`: SQL Server `4661160443904`, Snowflake `4649719431168`
- `{"business_date": "2026-09-30", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `bytes_used`: SQL Server `85251325952`, Snowflake `84089503744`
Explanation: Inherited from rate_overage (whole-GB integer truncation, invoiced) and rollup_storage_daily (storage day): bytes_used, overage_gb and overage_cents differ, see the rate_overage ledger entry for totals. PASS with legacy_overage_whole_gb_truncation=true and legacy_storage_day_eastern_fixed_offset=true. Finance decides at cutover.

### rpt_plan_mix

- `{"business_date": "2026-09-30", "plan_tier": "growth"}` `seat_count`: SQL Server `875`, Snowflake `800`
- `{"business_date": "2026-09-30", "plan_tier": "scale"}` `seat_count`: SQL Server `445`, Snowflake `400`
- `{"business_date": "2026-09-30", "plan_tier": "starter"}` `seat_count`: SQL Server `1329`, Snowflake `1199`
Explanation: Inherited from rollup_seats (users in two workspaces counted twice by the legacy procedure): seat_count and the columns derived from it differ (seat_limit and over_limit match). PASS with legacy_seats_count_workspace_memberships=true. Data owners decide.

### rpt_plan_tier_summary

- `{"business_date": "2026-09-30", "plan_tier": "growth"}` `seat_count`: SQL Server `875`, Snowflake `800`
Explanation: Inherited from rollup_seats (users in two workspaces counted twice by the legacy procedure): seat_count and the columns derived from it differ (seat_limit and over_limit match). PASS with legacy_seats_count_workspace_memberships=true. Data owners decide. The RDL passes @PlanTier='Growth' (title case) against lower-case data and relies on SQL Server's case-insensitive collation; the view's en-ci collation on plan_tier returns the same row in Snowflake (a case-sensitive comparison would return no rows).

### rpt_seat_count_by_tenant

- `{"business_date": "2026-09-30", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "040ef62f-cab7-4279-b317-8dbd18e12867"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "173d79f8-8296-4103-9432-264b163ebec5"}` `seat_count`: SQL Server `45`, Snowflake `40`
Explanation: Inherited from rollup_seats (users in two workspaces counted twice by the legacy procedure): seat_count and the columns derived from it differ (seat_limit and over_limit match). PASS with legacy_seats_count_workspace_memberships=true. Data owners decide.

### rpt_seat_limit_headroom

- `{"business_date": "2026-09-30", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "040ef62f-cab7-4279-b317-8dbd18e12867"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "173d79f8-8296-4103-9432-264b163ebec5"}` `seat_count`: SQL Server `45`, Snowflake `40`
Explanation: Inherited from rollup_seats (users in two workspaces counted twice by the legacy procedure): seat_count and the columns derived from it differ (seat_limit and over_limit match). PASS with legacy_seats_count_workspace_memberships=true. Data owners decide.

### rpt_seat_utilization

- `{"business_date": "2026-09-30", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "040ef62f-cab7-4279-b317-8dbd18e12867"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "173d79f8-8296-4103-9432-264b163ebec5"}` `seat_count`: SQL Server `45`, Snowflake `40`
Explanation: Inherited from rollup_seats (users in two workspaces counted twice by the legacy procedure): seat_count and the columns derived from it differ (seat_limit and over_limit match). PASS with legacy_seats_count_workspace_memberships=true. Data owners decide.

### rpt_seats_over_limit

- `{"business_date": "2026-09-30", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "173d79f8-8296-4103-9432-264b163ebec5"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "1b3e1a63-0f8f-4b5a-8a27-61ded31636fe"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "1d573d09-6ffc-401a-90d6-c424a7e95989"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "27557aaa-8749-43a8-91bc-1acd523bc5e0"}` `seat_count`: SQL Server `45`, Snowflake `40`
- `{"business_date": "2026-09-30", "tenant_id": "2b217fd0-6983-42aa-a5a9-14dbde5391fb"}` `seat_count`: SQL Server `45`, Snowflake `40`
Explanation: Inherited from rollup_seats (users in two workspaces counted twice by the legacy procedure): seat_count and the columns derived from it differ (seat_limit and over_limit match). PASS with legacy_seats_count_workspace_memberships=true. Data owners decide.

### rpt_storage_growth_trend

- `{"business_date": "2026-09-30", "observation_date": "2026-09-04", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `505723`, Snowflake `501432`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-05", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `510081`, Snowflake `509417`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-06", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `514319`, Snowflake `513574`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-08", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `523039`, Snowflake `522404`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-10", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `531364`, Snowflake `530887`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-11", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `536015`, Snowflake `531987`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-12", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `540486`, Snowflake `536339`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-14", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `548453`, Snowflake `545038`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-15", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `553614`, Snowflake `549154`
- `{"business_date": "2026-09-30", "observation_date": "2026-09-16", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `557548`, Snowflake `556811`
Explanation: Inherited from build_capacity_forecast_input (storage-day bucketing, 28-day window). Inherited from rollup_storage_daily (UTC day vs the legacy fixed -4h Eastern bucketing): only storage_peak_mb / bytes_used differ (and sums built from them). Snowflake is right; PASS with legacy_storage_day_eastern_fixed_offset=true (gate/out/legacy-flags/). Data owners decide.

### rpt_storage_vs_included

- `{"business_date": "2026-09-30", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `bytes_used`: SQL Server `648854634496`, Snowflake `648407941120`
- `{"business_date": "2026-09-30", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c"}` `overage_gb`: SQL Server `12`, Snowflake `12.846`
- `{"business_date": "2026-09-30", "tenant_id": "040ef62f-cab7-4279-b317-8dbd18e12867"}` `bytes_used`: SQL Server `591485992960`, Snowflake `590797078528`
- `{"business_date": "2026-09-30", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `bytes_used`: SQL Server `667042185216`, Snowflake `659711590400`
- `{"business_date": "2026-09-30", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `bytes_used`: SQL Server `77593575424`, Snowflake `76855377920`
- `{"business_date": "2026-09-30", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `bytes_used`: SQL Server `75139907584`, Snowflake `74479304704`
- `{"business_date": "2026-09-30", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `bytes_used`: SQL Server `55986618368`, Snowflake `55716085760`
- `{"business_date": "2026-09-30", "tenant_id": "154b7a42-20b5-4d23-8a24-54dfbc579609"}` `bytes_used`: SQL Server `62520295424`, Snowflake `62063116288`
- `{"business_date": "2026-09-30", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `bytes_used`: SQL Server `4661160443904`, Snowflake `4649719431168`
- `{"business_date": "2026-09-30", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `bytes_used`: SQL Server `85251325952`, Snowflake `84089503744`
Explanation: Inherited from rate_overage (whole-GB integer truncation, invoiced) and rollup_storage_daily (storage day): bytes_used, overage_gb and overage_cents differ, see the rate_overage ledger entry for totals. PASS with legacy_overage_whole_gb_truncation=true and legacy_storage_day_eastern_fixed_offset=true. Finance decides at cutover.

### rpt_tenant_storage_peak

- `{"business_date": "2026-09-30", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `storage_peak_mb`: SQL Server `618796`, Snowflake `618370`
- `{"business_date": "2026-09-30", "tenant_id": "040ef62f-cab7-4279-b317-8dbd18e12867"}` `storage_peak_mb`: SQL Server `564085`, Snowflake `563428`
- `{"business_date": "2026-09-30", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `storage_peak_mb`: SQL Server `636141`, Snowflake `629150`
- `{"business_date": "2026-09-30", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `storage_peak_mb`: SQL Server `73999`, Snowflake `73295`
- `{"business_date": "2026-09-30", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `storage_peak_mb`: SQL Server `71659`, Snowflake `71029`
- `{"business_date": "2026-09-30", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `storage_peak_mb`: SQL Server `53393`, Snowflake `53135`
- `{"business_date": "2026-09-30", "tenant_id": "154b7a42-20b5-4d23-8a24-54dfbc579609"}` `storage_peak_mb`: SQL Server `59624`, Snowflake `59188`
- `{"business_date": "2026-09-30", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `storage_peak_mb`: SQL Server `4445229`, Snowflake `4434318`
- `{"business_date": "2026-09-30", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `storage_peak_mb`: SQL Server `81302`, Snowflake `80194`
- `{"business_date": "2026-09-30", "tenant_id": "173d79f8-8296-4103-9432-264b163ebec5"}` `storage_peak_mb`: SQL Server `69274`, Snowflake `68763`
Explanation: Inherited from rollup_storage_daily (UTC day vs the legacy fixed -4h Eastern bucketing): only storage_peak_mb / bytes_used differ (and sums built from them). Snowflake is right; PASS with legacy_storage_day_eastern_fixed_offset=true (gate/out/legacy-flags/). Data owners decide.

### rpt_tenant_usage_by_region

- `{"business_date": "2026-09-30", "region_code": "ap-southeast-2"}` `bytes_used`: SQL Server `12088144560128`, Snowflake `12029756702720`
- `{"business_date": "2026-09-30", "region_code": "eu-central-1"}` `bytes_used`: SQL Server `13085358161920`, Snowflake `13057964113920`
- `{"business_date": "2026-09-30", "region_code": "eu-west-1"}` `bytes_used`: SQL Server `13688831475712`, Snowflake `13640857026560`
- `{"business_date": "2026-09-30", "region_code": "us-east-1"}` `bytes_used`: SQL Server `13544126939136`, Snowflake `13528903712768`
- `{"business_date": "2026-09-30", "region_code": "us-west-2"}` `bytes_used`: SQL Server `13243743469568`, Snowflake `13193704374272`
Explanation: Inherited from rollup_storage_daily (UTC day vs the legacy fixed -4h Eastern bucketing): only storage_peak_mb / bytes_used differ (and sums built from them). Snowflake is right; PASS with legacy_storage_day_eastern_fixed_offset=true (gate/out/legacy-flags/). Data owners decide.

### rpt_tenant_usage_daily

- `{"business_date": "2026-09-30", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `storage_peak_mb`: SQL Server `618796`, Snowflake `618370`
- `{"business_date": "2026-09-30", "tenant_id": "040ef62f-cab7-4279-b317-8dbd18e12867"}` `storage_peak_mb`: SQL Server `564085`, Snowflake `563428`
- `{"business_date": "2026-09-30", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `storage_peak_mb`: SQL Server `636141`, Snowflake `629150`
- `{"business_date": "2026-09-30", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `storage_peak_mb`: SQL Server `73999`, Snowflake `73295`
- `{"business_date": "2026-09-30", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `storage_peak_mb`: SQL Server `71659`, Snowflake `71029`
- `{"business_date": "2026-09-30", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `storage_peak_mb`: SQL Server `53393`, Snowflake `53135`
- `{"business_date": "2026-09-30", "tenant_id": "154b7a42-20b5-4d23-8a24-54dfbc579609"}` `storage_peak_mb`: SQL Server `59624`, Snowflake `59188`
- `{"business_date": "2026-09-30", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `storage_peak_mb`: SQL Server `4445229`, Snowflake `4434318`
- `{"business_date": "2026-09-30", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `storage_peak_mb`: SQL Server `81302`, Snowflake `80194`
- `{"business_date": "2026-09-30", "tenant_id": "173d79f8-8296-4103-9432-264b163ebec5"}` `storage_peak_mb`: SQL Server `69274`, Snowflake `68763`
Explanation: Inherited from rollup_storage_daily (UTC day vs the legacy fixed -4h Eastern bucketing): only storage_peak_mb / bytes_used differ (and sums built from them). Snowflake is right; PASS with legacy_storage_day_eastern_fixed_offset=true (gate/out/legacy-flags/). Data owners decide.

### rpt_tenant_usage_top20

- `{"business_date": "2026-09-30", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `storage_peak_mb`: SQL Server `636141`, Snowflake `629150`
- `{"business_date": "2026-09-30", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `storage_peak_mb`: SQL Server `4445229`, Snowflake `4434318`
- `{"business_date": "2026-09-30", "tenant_id": "212c0db7-dc12-4bb6-97fe-50a5096e8609"}` `storage_peak_mb`: SQL Server `4475142`, Snowflake `4435892`
- `{"business_date": "2026-09-30", "tenant_id": "25fea9ca-72dc-42d8-b6fb-3e7be292a1a0"}` `storage_peak_mb`: SQL Server `694411`, Snowflake `685988`
- `{"business_date": "2026-09-30", "tenant_id": "2a1db1ee-db91-47c2-9233-55190701e838"}` `storage_peak_mb`: SQL Server `648504`, Snowflake `646185`
- `{"business_date": "2026-09-30", "tenant_id": "32ee9387-ea76-4ab8-821c-a6097f34fb88"}` `storage_peak_mb`: SQL Server `628817`, Snowflake `628333`
- `{"business_date": "2026-09-30", "tenant_id": "38e979c2-2709-43ef-bf24-b824f410b873"}` `storage_peak_mb`: SQL Server `658725`, Snowflake `654270`
- `{"business_date": "2026-09-30", "tenant_id": "43cbcefc-2429-402a-bb14-9b50fb30468f"}` `storage_peak_mb`: SQL Server `664271`, Snowflake `663661`
- `{"business_date": "2026-09-30", "tenant_id": "4f7a5149-97af-4b8f-8cca-49809ddaf212"}` `storage_peak_mb`: SQL Server `668730`, Snowflake `665067`
- `{"business_date": "2026-09-30", "tenant_id": "6ec1190c-e799-4d58-9942-ccb5ad8f805a"}` `storage_peak_mb`: SQL Server `4095736`, Snowflake `4095641`
Explanation: Inherited from rollup_storage_daily (UTC day vs the legacy fixed -4h Eastern bucketing): only storage_peak_mb / bytes_used differ (and sums built from them). Snowflake is right; PASS with legacy_storage_day_eastern_fixed_offset=true (gate/out/legacy-flags/). Data owners decide. The top-20 set and order follow bytes_used.
