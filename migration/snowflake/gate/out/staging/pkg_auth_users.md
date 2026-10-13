Staging parity pkg_auth_users PASS 2400 / 2400 differing_keys=0

SQL Server `stg.stg_auth_users` vs Snowflake `STAGING.STG_AUTH_USERS`, keys id, 9 compared columns.

Not compared:
- `extracted_at`: @[System::StartTime] of the package run (SQL Server GETDATE() at replay); run-dependent load timestamp, Snowflake stamps current_timestamp() at query time

Transforms: `SQL Truncate stg_auth_users` then one data flow `auth_users.csv` -> `DER Normalise timestamps` -> `[stg].[stg_auth_users]`; no Lookup, no Conditional Split, no Script Task, no business-date or watermark dependency (full truncate and reload). Model `STAGING.STG_AUTH_USERS` (`target/dbt/models/staging/pkg_auth_users/stg_auth_users.sql`) reads `RAW.EXT_AUTH_USERS`.

### Business decisions

Explanation: Boolean flags default to false. `(DT_BOOL)(email_verified == "t")` and the same for `mfa_enabled` turn anything that is not exactly lowercase `t` (including `true`, `T`, `1`, or an empty field) into `0`. In the 2026-09-30 extract the field is always `t` or `f`: email_verified 2,057 true / 343 false, mfa_enabled 800 true / 1,600 false, so no row is currently defaulted. The model keeps `= 't'` (empty string -> false). A correct version would accept the usual true spellings and reject (or flag) unrecognised or missing values instead of silently reporting the user as unverified / without MFA.

Explanation: The UTC offset is stripped, not converted. `REPLACE(x, "+00", "")` then `(DT_DBTIMESTAMP2,7)` stores `created_at`, `updated_at` and `last_login_at` as zone-less `datetime2` that are implicitly UTC. All 2,400 created_at / updated_at values and 2,080 non-empty last_login_at values carry `+00`, so the stored instants are right today; 320 empty last_login_at become NULL. Any other offset (e.g. `+02`, `-05:00`) would either fail the cast or be stored as wall-clock time without shifting. The model reproduces it with `to_timestamp_ntz(replace(..., '+00', ''))`. A correct Snowflake version would parse the offset and store `TIMESTAMP_TZ` (or convert to UTC explicitly).

Explanation: `email_domain` falls back to the whole address. `LOWER(SUBSTRING(email, FINDSTRING(email,"@",1)+1, 255))` takes everything after the first `@`, lowercased and cut at 255 characters; when there is no `@`, FINDSTRING returns 0 and the "domain" is the entire lowercased email. 0 of 2,400 rows lack an `@` or have more than one, and none are mixed case, so no row is affected today. The model mirrors it with `lower(substr(email, position('@', email) + 1, 255))`. A correct version would return NULL for an address without `@` (the column is nullable) and split on the last `@`.

Not a decision: `extracted_at` is `@[System::StartTime]`, the legacy server's local (Eastern) clock; the model stamps `convert_timezone('America/New_York', current_timestamp())` and the column is excluded from comparison as run-dependent.
