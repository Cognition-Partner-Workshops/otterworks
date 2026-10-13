Staging parity pkg_documents PASS 40000 / 40000 differing_keys=0

`ssis:pkg_documents`: SQL Server `stg.stg_documents` vs Snowflake `STAGING.STG_DOCUMENTS`, keys id, 14 compared columns.
Not compared:
- `extracted_at`: run timestamp (@[System::StartTime] on SQL Server, dbt run_started_at in Snowflake); differs on every run

### Business decisions

Explanation: Missing `archived` stays unknown. The Derived Column `ISNULL(archived) ? NULL(DT_BOOL) : (DT_BOOL)(archived == "t")` lands a blank flag as NULL rather than defaulting it; 1,200 of 40,000 documents have `archived` NULL on 2026-09-30 (34,318 false, 4,482 true). The model keeps the NULL. A corrected Snowflake version would have the data owners pick an explicit default (or reject the row), because downstream document-status logic reads NULL as active.

Explanation: Tenant lookup never drops or fails a row. `LKP Tenant from workspace` reads `SELECT DISTINCT workspace_id, tenant_id FROM stg.stg_auth_workspace_members` and the package lands a document whose workspace has no member with a NULL `tenant_id`; a workspace with two tenants would get whichever row the cache kept last. On 2026-09-30 every one of the 180 workspaces matches exactly one tenant, so 0 rows are affected. The model keeps the left join (max tenant per workspace) and the singular test `pkg_documents__workspace_single_tenant` fails if a workspace ever gets a second tenant. A corrected version would send no-match rows to an error output instead of loading them tenant-less.

Explanation: Unknown boolean text becomes false. `(DT_BOOL)(is_deleted == "t")` and the same for `is_template` turn anything other than `t` (blank, `true`, `1`, `T`) into false rather than rejecting it. Today the file only holds `t`/`f` (is_deleted 1,600 t / 38,400 f, is_template 1,291 t / 38,709 f), so 0 rows are affected. The model reproduces `= 't'` with a false default; a stricter version would reject values outside `t`/`f`.

Explanation: Time zone dropped from timestamps. `(DT_DBTIMESTAMP2,7)REPLACE(created_at,"+00","")` (and `updated_at`) strips the `+00` offset and stores a naive `datetime2`, so the UTC meaning is only implied; all 40,000 rows carry `+00`, so no value shifts. The model does the same `replace(.., '+00', '')::timestamp_ntz`. A corrected version would parse the offset (`timestamp_tz`, or convert to UTC explicitly) so a non-UTC source value could not be loaded as if it were UTC.
