Staging parity pkg_auth_memberships PASS 2650 / 2650 differing_keys=0

SQL Server `stg.stg_auth_workspace_members` vs Snowflake `STAGING.STG_AUTH_WORKSPACE_MEMBERS`, keys user_id, workspace_id, 5 compared columns.

Not compared:
- `extracted_at`: @[System::StartTime] of the package run (SQL Server server clock); differs on every run on both sides

### Notes

- Compared: the SQL Server table written by `source/replay/ssis_replay.py`, which reads the package XML (flat-file connection manager over `auth_workspace_members.csv`, Execute SQL truncate, Derived Column `DER Normalise timestamps`, OLE DB destination) and does not execute SSIS or C#; the package has no Script Task, Lookup or Conditional Split.
- `BusinessDate` is declared but read by neither the truncate nor the data flow, so the package lands the same 2,650 rows for every date. Replayed and gated 2026-09-15 and 2026-09-30: PASS 2650 / 2650 on both; replay order has no effect on this table.
- This branch's `staging_parity.py` (older base) rewrites the whole markdown, so these two sections were re-appended after the gate run.

### Business decisions

Explanation: `joined_at` time-zone marker dropped. The Derived Column `(DT_DBTIMESTAMP2,7)REPLACE(joined_at,"+00","")` strips the `+00` UTC offset and lands the value as a zone-less `datetime2`; all 2,650 rows carry `+00` on both 2026-09-15 and 2026-09-30, so no value shifts, but the column is UTC only by convention (and a row with any other offset would fail the cast instead of being converted). The model keeps this (`to_timestamp_ntz` of the stripped text) so parity holds; test `pkg_auth_memberships__joined_at_offset_is_utc` flags any other offset. A cleaner Snowflake version would parse the offset into `TIMESTAMP_TZ` (or name the column `joined_at_utc`) so the zone is explicit.

Explanation: the business day of `joined_at` is the UTC day. `usp_load_dim_workspace` and `usp_rollup_seats` keep memberships with `joined_at < DATEADD(day, 1, @business_date)` on the zone-less UTC value, so a membership joined at 2026-09-16 00:00 UTC (2026-09-15 20:00 US Eastern, the SQL Server clock) is outside 2026-09-15: 1 row on 2026-09-15 (user `a6b4e1da-1338-472d-8ce2-dbb7ace87175`, workspace `6755e6e7-0f37-4a62-b228-c9c9b0b542e7`), 0 rows on 2026-09-30. Kept; the alternative (cut the day in US Eastern or the tenant's zone) would move that row into 2026-09-15 and is a decision for the seats/workspace rollups, not this staging table.

Explanation: one row per membership, and seats are counted per membership. The package lands every membership with no de-duplication: 2,650 rows for 2,400 users, of whom 250 belong to two workspaces (always in the same tenant; 0 users span tenants, so `usp_load_dim_user`'s `MIN(m.tenant_id)` changes nothing). `usp_rollup_seats` counts `COUNT(*)` over these rows (deliberate since 2017-02, "count from workspace membership so invited users show up"), so a user in two workspaces is two seats: on 2026-09-15 2,608 seats for 2,363 distinct users (245 users counted twice), on 2026-09-30 2,649 seats for 2,399 distinct users (250 counted twice). The staging model keeps every membership row so those numbers carry over; the alternative, `COUNT(DISTINCT user_id)` per tenant, would lower `seat_count` by 245 and 250 and belongs behind a var in the seats rollup port, not here.

Explanation: memberships of users not yet in `dim_user` are not seats. `usp_rollup_seats` inner-joins `dim.dim_user`, which holds only users with `created_at < DATEADD(day, 1, @business_date)`, so a membership whose `joined_at` is on or before the business date but whose user was created later is dropped: 13 memberships on 2026-09-15, 1 on 2026-09-30. This table keeps those rows (the package drops nothing); the alternative (count them, or join without the user-creation cut) would raise `seat_count` by 13 and 1 and is again the seats rollup's decision.
