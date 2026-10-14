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
| rollup_storage_daily | DIVERGE | 60 / 60 | 58 |
| rollup_usage_events | PASS | 7811 / 7811 | 0 |
| rollup_seats | DIVERGE | 60 / 60 | 50 |
| rollup_collab_daily | PASS | 1635 / 1635 | 0 |
| rollup_audit | PASS | 5024 / 5024 | 0 |
| rollup_document_status | DIVERGE | 360 / 540 | 360 |
| rollup_retention | PASS | 8448 / 8448 | 0 |
| build_invoice_lines | PASS | 376 / 376 | 0 |
| rate_overage | DIVERGE | 60 / 60 | 51 |
| apply_plan_limits | PASS | 60 / 60 | 0 |
| build_capacity_forecast_input | DIVERGE | 1680 / 1680 | 1632 |
| build_mart_tenant_usage | DIVERGE | 60 / 60 | 53 |
| build_mart_plan_seat_summary | DIVERGE | 3 / 3 | 3 |
| build_mart_overage | DIVERGE | 60 / 60 | 58 |
| build_mart_retention | PASS | 240 / 240 | 0 |
| build_mart_audit | PASS | 1909 / 1909 | 0 |
| log_run | DIVERGE | 47 / 35 | 13 |
| purge_expired | DIVERGE | 82 / 35 | 35 |

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
Explanation: Snowflake is right; the legacy number is wrong and it is the one finance has been looking at. dbo.usp_rollup_storage_daily buckets storage samples with CAST(DATEADD(hour, -4, event_ts_utc) AS date), a fixed US Eastern daylight offset, while every other fact uses the UTC day; the legacy row for a date takes 00:00-03:59 UTC of the next day and drops the same hours of its own day (e.g. 2026-09-30 tenant 06164f4b: legacy peak 636141 MB is a 2026-10-01 01:05 UTC sample, the UTC-day peak is 629150 MB), and the offset is an hour wrong whenever Eastern is on standard time. Sum of tenant peaks is +0.44% legacy on 2026-09-15 and +0.30% on 2026-09-30; plan_id and included_bytes match. Overage invoices are priced from this fact. Kept behind dbt var legacy_storage_day_eastern_fixed_offset=true, which reproduces the legacy rows exactly (gate PASS on both dates, gate/out/legacy-flags/). Decided at cutover by Finance and Billing: the corrected UTC-day number ships and the flag is off in the gated configuration.

### rollup_seats

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
Explanation: Source bug in the auth membership source that the reports have always reproduced. Decided at cutover by Finance and Billing: the corrected distinct-user count ships; the legacy count stays available to Billing behind legacy_seats_count_workspace_memberships=true, which is off in the gated configuration. dbo.usp_rollup_seats joins dim_user to every stg_auth_workspace_members row and COUNT(*)s, so the 250 users who belong to two workspaces of their tenant are counted twice (2650 membership rows for 2400 users). Seats: SQL Server 2608 / 2649, Snowflake 2363 / 2399 on 2026-09-15 / 2026-09-30; e.g. tenant 0052b048 45 vs 40. tenants over limit is unchanged (30, all starter tenants, either way). Snowflake counts each user once per tenant; dbt var legacy_seats_count_workspace_memberships=true reproduces the legacy count exactly (PASS, gate/out/legacy-flags/).

### rollup_document_status

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
Explanation: Legacy defect, not invoiced. dbo.usp_rollup_document_status uses CASE WHEN archived = 1 THEN 'archived' ELSE 'active', so the 1152 live documents whose archived flag is NULL (document-service never set it) are counted as active. Snowflake reports them under status_label 'unknown': active 33910 -> 32758 (2026-09-15) and 34066 -> 32914 (2026-09-30), archived identical, 180 extra 'unknown' rows. Snowflake is right; dbt var legacy_null_archived_counted_active=true reproduces the legacy split exactly (PASS). No invoice is computed from this table, so the corrected split is the default; rpt_document_status changes the same way.

### rate_overage

- `{"business_date": "2026-09-30", "tenant_id": "0052b048-57ff-4286-8f9c-181bfa4df6ed"}` `overage_gb`: SQL Server `104`, Snowflake `103.877`
- `{"business_date": "2026-09-30", "tenant_id": "01721f9d-08ad-4285-9cd3-ef8c4adde52c"}` `overage_gb`: SQL Server `12`, Snowflake `12.846`
- `{"business_date": "2026-09-30", "tenant_id": "040ef62f-cab7-4279-b317-8dbd18e12867"}` `overage_gb`: SQL Server `50`, Snowflake `50.223`
- `{"business_date": "2026-09-30", "tenant_id": "06164f4b-4188-45e5-b423-c8487896a014"}` `overage_gb`: SQL Server `121`, Snowflake `114.404`
- `{"business_date": "2026-09-30", "tenant_id": "0a7303a8-878d-4e1c-ae6f-1dcd5cc242c6"}` `overage_gb`: SQL Server `22`, Snowflake `21.577`
- `{"business_date": "2026-09-30", "tenant_id": "0ce98e8d-ca00-4ab0-8205-cd156818f096"}` `overage_gb`: SQL Server `19`, Snowflake `19.364`
- `{"business_date": "2026-09-30", "tenant_id": "12618590-5636-48ad-b3ad-1856de3130af"}` `overage_gb`: SQL Server `2`, Snowflake `1.890`
- `{"business_date": "2026-09-30", "tenant_id": "154b7a42-20b5-4d23-8a24-54dfbc579609"}` `overage_gb`: SQL Server `8`, Snowflake `7.801`
- `{"business_date": "2026-09-30", "tenant_id": "1682084f-1849-48df-bb8b-ebf1b3d4eced"}` `overage_gb`: SQL Server `29`, Snowflake `28.314`
- `{"business_date": "2026-09-30", "tenant_id": "173d79f8-8296-4103-9432-264b163ebec5"}` `overage_gb`: SQL Server `17`, Snowflake `17.151`
Explanation: Snowflake is right; the legacy number is wrong and customers have been invoiced on it. dbo.usp_rate_overage computes overage_gb = (bytes_used - included_bytes) / 1073741824 in bigint arithmetic, dropping every partial GB before pricing (tenant 01721f9d: 12.846 GB over billed as 12 GB). The difference also carries the storage-day shift from rollup_storage_daily. Overage: SQL Server 2029 GB / 31,423 cents (2026-09-15) and 5002 GB / 76,616 cents (2026-09-30); Snowflake prorated to the byte 1899.857 GB / 29,787 cents and 4903.461 GB / 75,243 cents (51 tenants with a charge vs 50). Kept behind dbt var legacy_overage_whole_gb_truncation=true (with legacy_storage_day_eastern_fixed_offset=true the unit PASSes on both dates). Decided at cutover by Finance and Billing: the byte-prorated number ships and invoices come from it; the flag is off in the gated configuration.

### build_capacity_forecast_input

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
Explanation: Inherited, two causes: observation days use the same fixed -4h Eastern bucketing as rollup_storage_daily (peak_storage_mb/bytes_used per day differ; on 2026-09-15 the 28-day window also holds 926 vs 960 tenant-days because the legacy Eastern day 2026-08-31 takes the 2026-09-01 00:00-03:59 UTC samples of all 60 tenants (16 x 60 = 960), while the UTC day 2026-08-31 holds only the 26 tenants whose first sample was jittered before midnight (15 x 60 + 26 = 926; MARTS.BUILD_CAPACITY_FORECAST_INPUT has 26 rows for observation_date 2026-08-31)), and seat_count follows rollup_seats. PASS with legacy_storage_day_eastern_fixed_offset=true and legacy_seats_count_workspace_memberships=true. Decided at cutover: the corrected numbers ship for both causes, flags off.

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
Explanation: Inherited from rollup_storage_daily, not a separate defect: only storage_peak_mb and bytes_used differ, copied from fact_storage_usage_daily by dbo.usp_build_mart_tenant_usage; every other column matches for all 60 tenants. Snowflake (UTC day) is right; the usage pages, the eight rpt_tenant_* reports, admin-dashboard and analytics-service have shown the legacy Eastern-offset peak. PASS with legacy_storage_day_eastern_fixed_offset=true. Decided at cutover, as for rollup_storage_daily: the corrected UTC-day number ships.

### build_mart_plan_seat_summary

- `{"business_date": "2026-09-30", "plan_tier": "growth"}` `seat_count`: SQL Server `875`, Snowflake `800`
- `{"business_date": "2026-09-30", "plan_tier": "scale"}` `seat_count`: SQL Server `445`, Snowflake `400`
- `{"business_date": "2026-09-30", "plan_tier": "starter"}` `seat_count`: SQL Server `1329`, Snowflake `1199`
Explanation: Inherited from rollup_seats: seat_count and avg_seats_per_tenant per tier are lower by the double-counted memberships (growth 863->789, 875->800 seats; avg 43.15->39.45, 43.75->40.00); tenant_count, seat_limit_total and tenants_over_limit match. PASS with legacy_seats_count_workspace_memberships=true. Decided at cutover, as for rollup_seats: the corrected count ships; the legacy count stays available to Billing behind the flag.

### build_mart_overage

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
Explanation: Inherited from rate_overage and rollup_storage_daily: bytes_used (storage day), overage_gb and overage_cents (whole-GB truncation) differ; tenant, tier, included_bytes and rate match. This is the table export_overage.sh and the three overage reports read. PASS with both legacy flags. Decided at cutover, as for rate_overage: the corrected number ships.

### log_run

- `{"business_date": "2026-09-30", "object_name": "pkg_analytics"}` `<duplicate key>`: SQL Server `2 rows`, Snowflake `1 rows`
- `{"business_date": "2026-09-30", "object_name": "pkg_audit"}` `<duplicate key>`: SQL Server `2 rows`, Snowflake `1 rows`
- `{"business_date": "2026-09-30", "object_name": "pkg_auth_memberships"}` `<duplicate key>`: SQL Server `2 rows`, Snowflake `1 rows`
- `{"business_date": "2026-09-30", "object_name": "pkg_auth_users"}` `<duplicate key>`: SQL Server `2 rows`, Snowflake `1 rows`
- `{"business_date": "2026-09-30", "object_name": "pkg_billing_core"}` `<duplicate key>`: SQL Server `2 rows`, Snowflake `1 rows`
- `{"business_date": "2026-09-30", "object_name": "pkg_billing_invoices"}` `<duplicate key>`: SQL Server `2 rows`, Snowflake `1 rows`
- `{"business_date": "2026-09-30", "object_name": "pkg_billing_usage"}` `<duplicate key>`: SQL Server `2 rows`, Snowflake `1 rows`
- `{"business_date": "2026-09-30", "object_name": "pkg_collaboration"}` `<duplicate key>`: SQL Server `2 rows`, Snowflake `1 rows`
- `{"business_date": "2026-09-30", "object_name": "pkg_document_versions"}` `<duplicate key>`: SQL Server `2 rows`, Snowflake `1 rows`
- `{"business_date": "2026-09-30", "object_name": "pkg_documents"}` `<duplicate key>`: SQL Server `2 rows`, Snowflake `1 rows`
Explanation: Operational log, not a business number. On 2026-09-30 the legacy ops.etl_run_log holds two rows per package for the same business date (sfm-up's initial package replay and the nightly job both log 2026-09-30), so the key (business_date, object_name) is not unique on the SQL Server side and the gate reports those 12 packages as duplicate keys, and the 13th differing key is usp_rollup_document_status (rows_written 360 vs 540, the row count of the document-status model that diverges by design); on 2026-09-15 (one nightly run) only usp_build_capacity_forecast_input and usp_rollup_document_status differ, which are the row counts of the two models that diverge by design above. Every other object's rows_written matches. Accepted: Snowflake logs each step once per business date (OPS.LOG_RUN), the task graph's own step log is OPS.ETL_RUN_LOG.

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
