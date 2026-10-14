Parity PASS=9 DIVERGE=2 PENDING=14

| Unit | Status | Rows (SQL Server / Snowflake) | Differing keys |
| --- | --- | ---: | ---: |
| load_dim_date | PASS | 3926 / 3926 | 0 |
| load_dim_tenant | PASS | 60 / 60 | 0 |
| load_dim_plan | PASS | 7 / 7 | 0 |
| load_dim_user | PASS | 2399 / 2399 | 0 |
| load_dim_workspace | PASS | 180 / 180 | 0 |
| load_dim_document | PASS | 39982 / 39982 | 0 |
| load_dim_file | PASS | 24993 / 24993 | 0 |
| rollup_storage_daily | DIVERGE | 60 / 60 | 58 |
| rollup_usage_events | PASS | 7811 / 7811 | 0 |
| rollup_seats | PENDING | 0 / 0 | 0 |
| rollup_collab_daily | PENDING | 0 / 0 | 0 |
| rollup_audit | PASS | 5024 / 5024 | 0 |
| rollup_document_status | PENDING | 0 / 0 | 0 |
| rollup_retention | PENDING | 0 / 0 | 0 |
| build_invoice_lines | PENDING | 0 / 0 | 0 |
| rate_overage | PENDING | 0 / 0 | 0 |
| apply_plan_limits | PENDING | 0 / 0 | 0 |
| build_capacity_forecast_input | PENDING | 0 / 0 | 0 |
| build_mart_tenant_usage | DIVERGE | 60 / 60 | 53 |
| build_mart_plan_seat_summary | PENDING | 0 / 0 | 0 |
| build_mart_overage | PENDING | 0 / 0 | 0 |
| build_mart_retention | PENDING | 0 / 0 | 0 |
| build_mart_audit | PENDING | 0 / 0 | 0 |
| log_run | PENDING | 0 / 0 | 0 |
| purge_expired | PENDING | 0 / 0 | 0 |

### rollup_storage_daily

- `{"business_date": "2026-09-30", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `sample_count`: SQL Server `23`, Snowflake `25`
- `{"business_date": "2026-09-30", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c"}` `sample_count`: SQL Server `23`, Snowflake `24`
- `{"business_date": "2026-09-30", "tenant_id": "040ef62f-cab7-4279-b317-8dbd18e12867"}` `sample_count`: SQL Server `25`, Snowflake `24`
- `{"business_date": "2026-09-30", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `peak_storage_mb`: SQL Server `636141`, Snowflake `629150`
- `{"business_date": "2026-09-30", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `sample_count`: SQL Server `24`, Snowflake `23`
- `{"business_date": "2026-09-30", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `sample_count`: SQL Server `24`, Snowflake `23`
- `{"business_date": "2026-09-30", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `peak_storage_mb`: SQL Server `53393`, Snowflake `53135`
- `{"business_date": "2026-09-30", "tenant_id": "154b7a42-20b5-4d23-8a24-54dfbc579609"}` `sample_count`: SQL Server `24`, Snowflake `25`
- `{"business_date": "2026-09-30", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `sample_count`: SQL Server `24`, Snowflake `23`
- `{"business_date": "2026-09-30", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `sample_count`: SQL Server `23`, Snowflake `25`
Explanation: Snowflake is right; the legacy number is wrong and it is the one finance has been looking at. dbo.usp_rollup_storage_daily buckets samples with CAST(DATEADD(hour, -4, event_ts_utc) AS date), a fixed US Eastern daylight offset, while every other fact (usage events, audit, invoices, dims) uses the UTC day the timestamps arrive in. The legacy 2026-09-30 row therefore takes the four hours 2026-10-01 00:00-03:59 UTC (October samples) and drops 2026-09-30 00:00-03:59 UTC; e.g. tenant 06164f4b: legacy peak 636141 MB is a sample at 2026-10-01 01:05 UTC, the UTC-day peak is 629150 MB. The offset is also an hour wrong every day US Eastern is on standard time. Size: sum of tenant peaks is 57,611,251 MB legacy vs 57,357,765 MB UTC on 2026-09-15 (legacy +0.44%) and 62,608,914 vs 62,419,115 MB on 2026-09-30 (+0.30%); 59 of 60 tenants (2026-09-15) and 58 of 60 (2026-09-30) differ in sample_count and/or peak_storage_mb, plan_id and included_bytes match. Because usp_rate_overage prices overage from this fact, legacy overage invoices have been computed from the shifted peak. The model defaults to the UTC day; dbt var legacy_storage_day_eastern_fixed_offset=true reproduces the legacy rows exactly (gate PASS on both dates with it on). Data owners (Finance + Billing) decide whether invoices switch to the UTC day at cutover.

### build_mart_tenant_usage

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
Explanation: Inherited from rollup_storage_daily, not a separate defect: only storage_peak_mb and bytes_used differ, and they are copied from fact_storage_usage_daily by dbo.usp_build_mart_tenant_usage. All other columns (tenant, tier, region, api/compute units, active users, document and file counts) match for all 60 tenants. Snowflake (UTC day) is right; the usage pages, the eight rpt_tenant_* reports, admin-dashboard and analytics-service have shown the legacy Eastern-offset peak. With legacy_storage_day_eastern_fixed_offset=true this unit passes too. Same data-owner decision as rollup_storage_daily.
