Staging parity pkg_audit PASS 160000 / 160000 differing_keys=0

`ssis:pkg_audit`: SQL Server `stg.stg_audit_events` vs Snowflake `STAGING.STG_AUDIT_EVENTS`, keys id, 10 compared columns.
Not compared:
- `extracted_at`: run timestamp: @[System::StartTime] of the SSIS run vs dbt run_started_at

### Business decisions

Explanation: Tenant attribution by MIN(tenant_id). `LKP Tenant from user` joins each audit event on user_id to `SELECT user_id, MIN(tenant_id) FROM stg.stg_auth_workspace_members GROUP BY user_id`, so a user who belongs to several tenants has every audit event attributed to the lowest tenant id, whatever resource the event touched. On the 2026-09-30 data 250 of 2,400 users sit in more than one workspace (16,472 of 160,000 events), but all of them within a single tenant, so the rule changes 0 rows today. The model keeps the MIN rule; a correct version would attribute the event through the resource's own workspace/tenant, or flag users that resolve to more than one tenant.

Explanation: Lookup no-match keeps the row with a NULL tenant_id. Events whose user_id is not in stg_auth_workspace_members are not dropped or redirected; they land with tenant_id NULL (the column is nullable) and usp_rollup_audit then carries them into fact_audit_events without a tenant. 0 of 160,000 rows are unmatched on this extract. The model reproduces it with a LEFT JOIN; a correct version would quarantine unmatched events or assign an explicit "unknown tenant" so they are visible in tenant reporting.

Explanation: Timestamp truncated to microseconds. The file carries 7 fractional digits (`2026-09-18T02:18:48.0576402Z`); `DER Normalise timestamps` strips the Z and casts to DT_DBTIMESTAMP2,7, and the landed datetime2 values have the 100 ns digit zeroed (`.0576400`): 144,150 of 160,000 rows lose up to 0.9 µs. The Z is dropped without any offset shift, so the value stays UTC wall-clock. The model truncates to microseconds the same way; a correct version would keep the full 7-digit precision (TIMESTAMP_NTZ(9)), which changes no UTC day or ordering at second level.
