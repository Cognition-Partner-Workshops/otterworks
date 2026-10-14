Staging parity pkg_audit PASS 160000 / 160000 differing_keys=0

`ssis:pkg_audit`: SQL Server `stg.stg_audit_events` vs Snowflake `STAGING.STG_AUDIT_EVENTS`, keys id, 10 compared columns.
Not compared:
- `extracted_at`: run timestamp: @[System::StartTime] of the SSIS run vs dbt run_started_at

Compared: the SQL Server side is the replay of `pkg_audit.dtsx` by `source/replay/ssis_replay.py`, which interprets the package XML in Python; it does not execute SSIS. The package has no Script Task. `BusinessDate` is a package parameter that the data flow never reads, so 2026-09-15 and 2026-09-30 load the same 160,000 rows; both dates were replayed, built and gated (PASS 160000 / 160000 on each).

### Business decisions

Explanation: Tenant attribution by MIN(tenant_id). `LKP Tenant from user` joins each audit event on user_id to `SELECT user_id, MIN(tenant_id) AS tenant_id FROM stg.stg_auth_workspace_members GROUP BY user_id`, so a user who belongs to several tenants has every audit event attributed to the lowest tenant id, whatever resource the event touched. On both 2026-09-15 and 2026-09-30, 250 of 2,400 users sit in more than one workspace (16,472 of 160,000 events), but each of them within a single tenant, so the rule changes 0 rows on either date. The model keeps the MIN rule; the alternative is to attribute the event through the resource's own workspace/tenant, or flag users that resolve to more than one tenant.

Explanation: Lookup no-match keeps the row with a NULL tenant_id. Events whose user_id has no row in stg_auth_workspace_members are not dropped or redirected; they land with tenant_id NULL and usp_rollup_audit carries them into fact_audit_events without a tenant. 0 of 160,000 rows are unmatched on 2026-09-15 and 0 of 160,000 on 2026-09-30. The model reproduces it with a LEFT JOIN; the alternative is to quarantine unmatched events or assign an explicit "unknown tenant" so they show up in tenant reporting.

Explanation: Timestamp truncated to microseconds. The file carries 7 fractional digits (`2026-09-18T02:18:48.0576402Z`); `DER Normalise timestamps` is `(DT_DBTIMESTAMP2,7)REPLACE(timestamp,"Z","")`, and the landed datetime2 values have the 100 ns digit zeroed (`2026-09-18 02:18:48.0576400`). In the replay the zeroing comes from the cast going through a Python datetime (microsecond resolution); the column itself is datetime2(7). 144,150 of 160,000 rows lose their nonzero seventh digit (up to 0.9 µs) on 2026-09-15 and the same 144,150 on 2026-09-30. The Z is dropped with no offset shift, so the value stays UTC wall-clock. The model truncates to microseconds by default and the singular test `pkg_audit__timestamp_microseconds` holds it there, because the gate compares Python datetimes and cannot see the seventh digit either way; `--vars '{pkg_audit_timestamp_full_precision: true}'` keeps the full 7 digits instead, which changes no UTC business day and no ordering coarser than a microsecond.
