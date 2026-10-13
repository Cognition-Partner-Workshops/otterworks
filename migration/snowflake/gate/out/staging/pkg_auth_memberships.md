Staging parity pkg_auth_memberships PASS 2650 / 2650 differing_keys=0

SQL Server `stg.stg_auth_workspace_members` vs Snowflake `STAGING.STG_AUTH_WORKSPACE_MEMBERS`, keys user_id, workspace_id, 5 compared columns.

Not compared:
- `extracted_at`: @[System::StartTime] of the package run (SQL Server server clock); differs on every run on both sides

### Business decisions

Explanation: `joined_at` time-zone marker dropped. The Derived Column `(DT_DBTIMESTAMP2,7)REPLACE(joined_at,"+00","")` strips the `+00` UTC offset and lands the value as a zone-less `datetime2`; all 2,650 rows carry `+00`, so no value shifts, but the column is UTC only by convention (and a row with any other offset would fail the cast instead of being converted). The model keeps this (`to_timestamp_ntz` of the stripped text) so parity holds. A cleaner Snowflake version would parse the offset into `TIMESTAMP_TZ` (or name the column `joined_at_utc`) so the zone is explicit.
