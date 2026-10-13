Staging parity pkg_analytics PASS 120000 / 120000 differing_keys=0

`ssis:pkg_analytics`: SQL Server `stg.stg_analytics_events` vs Snowflake `STAGING.STG_ANALYTICS_EVENTS`, keys event_id, 10 compared columns.
Not compared:
- `extracted_at`: run timestamp (@[System::StartTime] on SQL Server, dbt run_started_at in Snowflake)

### Business decisions

Explanation: `event_ts_utc` truncates to the whole second. The package computes `DATEADD("ss", (DT_I4)(occurred_at / 1000000000), 1970-01-01)`, so the nanosecond epoch in `occurred_at` loses its sub-second part on every row (120,000 of 120,000 rows on 2026-09-30), and the `(DT_I4)` cast would overflow for events after 2038-01-19. The model keeps the truncation (`trunc(occurred_at / 1e9)` seconds) so parity passes; a correct Snowflake version would use `to_timestamp_ntz(occurred_at, 9)` and keep the full precision with no 2038 limit.

Explanation: `tenant_id` comes from a Lookup on `SELECT user_id, MIN(tenant_id) FROM stg.stg_auth_workspace_members GROUP BY user_id`: a user who belongs to workspaces in several tenants is credited to the alphabetically lowest tenant id, and an event whose user has no membership is kept with a NULL `tenant_id`. On 2026-09-30, 250 users have more than one membership row (12,615 events), but every one of them stays inside a single tenant, so the MIN rule changes no value today, and no event goes unmatched (0 NULL tenant ids). The model keeps both rules; a correct version would take the tenant from the event's own workspace or resource rather than the user, or flag users in more than one tenant instead of picking one.
