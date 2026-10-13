Parity PASS=15 DIVERGE=10 PENDING=0

| Unit | Status | Rows (SQL Server / Snowflake) | Differing keys |
| --- | --- | ---: | ---: |
| load_dim_date | PASS | 3926 / 3926 | 0 |
| load_dim_tenant | PASS | 60 / 60 | 0 |
| load_dim_plan | PASS | 7 / 7 | 0 |
| load_dim_user | PASS | 2399 / 2399 | 0 |
| load_dim_workspace | PASS | 180 / 180 | 0 |
| load_dim_document | PASS | 39982 / 39982 | 0 |
| load_dim_file | PASS | 24993 / 24993 | 0 |
| rollup_storage_daily | DIVERGE | 60 / 60 | 59 |
| rollup_usage_events | PASS | 7789 / 7789 | 0 |
| rollup_seats | DIVERGE | 60 / 60 | 50 |
| rollup_collab_daily | PASS | 1529 / 1529 | 0 |
| rollup_audit | PASS | 5187 / 5187 | 0 |
| rollup_document_status | DIVERGE | 360 / 540 | 360 |
| rollup_retention | PASS | 8388 / 8388 | 0 |
| build_invoice_lines | PASS | 184 / 184 | 0 |
| rate_overage | DIVERGE | 60 / 60 | 40 |
| apply_plan_limits | PASS | 60 / 60 | 0 |
| build_capacity_forecast_input | DIVERGE | 960 / 926 | 933 |
| build_mart_tenant_usage | DIVERGE | 60 / 60 | 52 |
| build_mart_plan_seat_summary | DIVERGE | 3 / 3 | 3 |
| build_mart_overage | DIVERGE | 60 / 60 | 58 |
| build_mart_retention | PASS | 240 / 240 | 0 |
| build_mart_audit | PASS | 1928 / 1928 | 0 |
| log_run | DIVERGE | 35 / 35 | 2 |
| purge_expired | DIVERGE | 82 / 35 | 35 |

### rollup_storage_daily

- `{"business_date": "2026-09-15", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `peak_storage_mb`: SQL Server `553614`, Snowflake `549154`
- `{"business_date": "2026-09-15", "tenant_id": "040ef62f-cab7-4279-b317-8dbd18e12867"}` `sample_count`: SQL Server `23`, Snowflake `25`
- `{"business_date": "2026-09-15", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `sample_count`: SQL Server `25`, Snowflake `23`
- `{"business_date": "2026-09-15", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `sample_count`: SQL Server `23`, Snowflake `25`
- `{"business_date": "2026-09-15", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `sample_count`: SQL Server `25`, Snowflake `24`
- `{"business_date": "2026-09-15", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `peak_storage_mb`: SQL Server `43511`, Snowflake `43015`
- `{"business_date": "2026-09-15", "tenant_id": "154b7a42-20b5-4d23-8a24-54dfbc579609"}` `sample_count`: SQL Server `24`, Snowflake `23`
- `{"business_date": "2026-09-15", "tenant_id": "155a3480-6695-427d-808a-14101dccaaf4"}` `sample_count`: SQL Server `23`, Snowflake `24`
- `{"business_date": "2026-09-15", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `peak_storage_mb`: SQL Server `65851`, Snowflake `64907`
- `{"business_date": "2026-09-15", "tenant_id": "173d79f8-8296-4103-9432-264b163ebec5"}` `sample_count`: SQL Server `25`, Snowflake `24`
Explanation: Snowflake is right; the legacy number is wrong and it is the one finance has been looking at. dbo.usp_rollup_storage_daily buckets storage samples with CAST(DATEADD(hour, -4, event_ts_utc) AS date), a fixed US Eastern daylight offset, while every other fact uses the UTC day; the legacy row for a date takes 00:00-03:59 UTC of the next day and drops the same hours of its own day (e.g. 2026-09-30 tenant 06164f4b: legacy peak 636141 MB is a 2026-10-01 01:05 UTC sample, the UTC-day peak is 629150 MB), and the offset is an hour wrong whenever Eastern is on standard time. Sum of tenant peaks is +0.44% legacy on 2026-09-15 and +0.30% on 2026-09-30; plan_id and included_bytes match. Overage invoices are priced from this fact. Kept behind dbt var legacy_storage_day_eastern_fixed_offset=true, which reproduces the legacy rows exactly (gate PASS on both dates, gate/out/legacy-flags/). Data owners (Finance + Billing) decide at cutover.

### rollup_seats

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
Explanation: Source bug the reports have always reproduced; data owners decide whether it survives. dbo.usp_rollup_seats joins dim_user to every stg_auth_workspace_members row and COUNT(*)s, so the 250 users who belong to two workspaces of their tenant are counted twice (2650 membership rows for 2400 users). Seats: SQL Server 2608 / 2649, Snowflake 2363 / 2399 on 2026-09-15 / 2026-09-30; e.g. tenant 0052b048 45 vs 40. tenants over limit is unchanged (30, all starter tenants, either way). Snowflake counts each user once per tenant; dbt var legacy_seats_count_workspace_memberships=true reproduces the legacy count exactly (PASS, gate/out/legacy-flags/).

### rollup_document_status

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
Explanation: Legacy defect, not invoiced. dbo.usp_rollup_document_status uses CASE WHEN archived = 1 THEN 'archived' ELSE 'active', so the 1152 live documents whose archived flag is NULL (document-service never set it) are counted as active. Snowflake reports them under status_label 'unknown': active 33910 -> 32758 (2026-09-15) and 34066 -> 32914 (2026-09-30), archived identical, 180 extra 'unknown' rows. Snowflake is right; dbt var legacy_null_archived_counted_active=true reproduces the legacy split exactly (PASS). No invoice is computed from this table, so the corrected split is the default; rpt_document_status changes the same way.

### rate_overage

- `{"business_date": "2026-09-15", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `overage_gb`: SQL Server `40`, Snowflake `36.283`
- `{"business_date": "2026-09-15", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c"}` `overage_gb`: SQL Server `3`, Snowflake `3.731`
- `{"business_date": "2026-09-15", "tenant_id": "040ef62f-cab7-4279-b317-8dbd18e12867"}` `overage_gb`: SQL Server `14`, Snowflake `14.733`
- `{"business_date": "2026-09-15", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `overage_gb`: SQL Server `17`, Snowflake `10.277`
- `{"business_date": "2026-09-15", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `overage_gb`: SQL Server `9`, Snowflake `9.991`
- `{"business_date": "2026-09-15", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `overage_gb`: SQL Server `10`, Snowflake `9.418`
- `{"business_date": "2026-09-15", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `overage_gb`: SQL Server `14`, Snowflake `13.386`
- `{"business_date": "2026-09-15", "tenant_id": "173d79f8-8296-4103-9432-264b163ebec5"}` `overage_gb`: SQL Server `4`, Snowflake `3.140`
- `{"business_date": "2026-09-15", "tenant_id": "1d573d09-6ffc-401a-90d6-c424a7e95989"}` `overage_gb`: SQL Server `16`, Snowflake `15.476`
- `{"business_date": "2026-09-15", "tenant_id": "22ee38da-0421-4404-aa99-73730eff7c22"}` `overage_gb`: SQL Server `38`, Snowflake `36.936`
Explanation: Snowflake is right; the legacy number is wrong and customers have been invoiced on it. dbo.usp_rate_overage computes overage_gb = (bytes_used - included_bytes) / 1073741824 in bigint arithmetic, dropping every partial GB before pricing (tenant 01721f9d: 12.846 GB over billed as 12 GB). The difference also carries the storage-day shift from rollup_storage_daily. Overage: SQL Server 2029 GB / 31,423 cents (2026-09-15) and 5002 GB / 76,616 cents (2026-09-30); Snowflake prorated to the byte 1899.857 GB / 29,787 cents and 4903.461 GB / 75,243 cents (51 tenants with a charge vs 50). Kept behind dbt var legacy_overage_whole_gb_truncation=true (with legacy_storage_day_eastern_fixed_offset=true the unit PASSes on both dates). Finance decides at cutover; until then do not invoice from the default numbers without that decision.

### build_capacity_forecast_input

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
Explanation: Inherited, two causes: observation days use the same fixed -4h Eastern bucketing as rollup_storage_daily (peak_storage_mb/bytes_used per day differ; on 2026-09-15 the 28-day window also holds 926 vs 960 tenant-days because the legacy window reaches into 2026-08-18 Eastern), and seat_count follows rollup_seats. PASS with legacy_storage_day_eastern_fixed_offset=true and legacy_seats_count_workspace_memberships=true. Same data-owner decisions.

### build_mart_tenant_usage

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
Explanation: Inherited from rollup_storage_daily, not a separate defect: only storage_peak_mb and bytes_used differ, copied from fact_storage_usage_daily by dbo.usp_build_mart_tenant_usage; every other column matches for all 60 tenants. Snowflake (UTC day) is right; the usage pages, the eight rpt_tenant_* reports, admin-dashboard and analytics-service have shown the legacy Eastern-offset peak. PASS with legacy_storage_day_eastern_fixed_offset=true. Same data-owner decision as rollup_storage_daily.

### build_mart_plan_seat_summary

- `{"business_date": "2026-09-15", "plan_tier": "growth"}` `seat_count`: SQL Server `863`, Snowflake `789`
- `{"business_date": "2026-09-15", "plan_tier": "scale"}` `seat_count`: SQL Server `438`, Snowflake `393`
- `{"business_date": "2026-09-15", "plan_tier": "starter"}` `seat_count`: SQL Server `1307`, Snowflake `1181`
Explanation: Inherited from rollup_seats: seat_count and avg_seats_per_tenant per tier are lower by the double-counted memberships (growth 863->789, 875->800 seats; avg 43.15->39.45, 43.75->40.00); tenant_count, seat_limit_total and tenants_over_limit match. PASS with legacy_seats_count_workspace_memberships=true. Same data-owner decision as rollup_seats.

### build_mart_overage

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
Explanation: Inherited from rate_overage and rollup_storage_daily: bytes_used (storage day), overage_gb and overage_cents (whole-GB truncation) differ; tenant, tier, included_bytes and rate match. This is the table export_overage.sh and the three overage reports read. PASS with both legacy flags. Finance decides.

### log_run

- `{"business_date": "2026-09-15", "object_name": "usp_build_capacity_forecast_input"}` `rows_written`: SQL Server `960`, Snowflake `926`
- `{"business_date": "2026-09-15", "object_name": "usp_rollup_document_status"}` `rows_written`: SQL Server `360`, Snowflake `540`
Explanation: Operational log, not a business number. On 2026-09-30 the legacy ops.etl_run_log holds two rows per package for the same business date (sfm-up's initial package replay and the nightly job both log 2026-09-30), so the key (business_date, object_name) is not unique on the SQL Server side and the gate reports those 12 packages as duplicate keys; on 2026-09-15 (one nightly run) only usp_build_capacity_forecast_input and usp_rollup_document_status differ, which are the row counts of the two models that diverge by design above. Every other object's rows_written matches. Accepted: Snowflake logs each step once per business date (OPS.LOG_RUN), the task graph's own step log is OPS.ETL_RUN_LOG.

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
