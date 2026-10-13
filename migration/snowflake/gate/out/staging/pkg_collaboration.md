Staging parity pkg_collaboration PASS 50000 / 50000 differing_keys=0

SQL Server `stg.stg_collab_events` vs Snowflake `STAGING.STG_COLLAB_EVENTS`, keys id, 7 compared columns.

Not compared:
- `extracted_at`: run timestamp (@[System::StartTime] on SQL Server, dbt run_started_at in Snowflake); differs on every run

### Business decisions

Explanation: Tenant lookup never drops or fails a row. `LKP Tenant from document` reads `SELECT id AS document_id, tenant_id FROM stg.stg_documents` and the package lands an event whose document is not in `stg_documents` with a NULL `tenant_id`; `usp_rollup_collab_daily` then silently skips those rows (`WHERE c.tenant_id IS NOT NULL`). On 2026-09-30 all 50,000 events match a document that has a tenant, so 0 rows are affected. The model keeps the left join (the singular test `pkg_collaboration__document_id_unique_in_lookup` guards against a fan-out). A corrected version would send no-match events to an error output or quarantine table instead of loading them tenant-less.

Explanation: Time zone dropped from timestamps. `(DT_DBTIMESTAMP2,7)REPLACE(created_at,"+00","")` strips the `+00` offset and stores a naive `datetime2`, so the UTC meaning is only implied; all 50,000 rows carry `+00`, so no value shifts. The model does the same `replace(.., '+00', '')::timestamp_ntz(7)`. A corrected version would parse the offset (`timestamp_tz`, or convert to UTC explicitly) so a non-UTC source value could not be loaded as if it were UTC.

Explanation: The business date is not applied. The package truncates `stg.stg_collab_events` and reloads the whole `collab_events.csv`; the `BusinessDate` parameter is never read, so the 2026-09-30 run lands 1,596 events dated 2026-10-01 (after the business date) alongside 46,740 earlier events and 1,664 on the day itself. The date filter only happens later in `usp_rollup_collab_daily`. The model also loads every row and ignores `var('business_date')`. A corrected version would bound the load to the business date window (or make it incremental) so future-dated events are not staged early.
