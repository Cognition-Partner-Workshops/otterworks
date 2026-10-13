Staging parity pkg_file_versions PASS 49999 / 49999 differing_keys=0

SQL Server `stg.stg_file_versions` vs Snowflake `STAGING.STG_FILE_VERSIONS`, keys file_id, version, 4 compared columns.

Not compared:
- `extracted_at`: @[System::StartTime] of the package run; differs on every run on both sides

### Business decisions

Explanation: The package has no date filter: it truncates `stg.stg_file_versions` and reloads the whole of file_versions.csv whatever `BusinessDate` is. The extract is taken at 2026-10-01 23:59:59 UTC, so for business date 2026-09-30 it lands 940 of 49,999 version rows whose `created_at` is on 2026-10-01 (UTC; 924 of them clamped to the extract time 23:59:59), and for 2026-09-15 the same 1,206 rows created after that day. `usp_load_dim_file` then counts them in `dim_file.version_count` with no date cut on the versions. The dbt model keeps this (no `business_date` filter) so parity holds; a corrected version would keep only versions with `created_at < business_date + 1 day` (in the warehouse's reporting zone), or move that cut into the dim_file model.

Explanation: `DER Normalise timestamps` turns the RFC 3339 UTC string (e.g. `2017-01-06T01:30:49.094Z`) into a zone-less `datetime2` by deleting the `T` and the `Z`, so `created_at` is UTC wall-clock time with the zone marker thrown away, on a server whose clock is America/New_York. All 49,999 rows are affected; nothing is shifted. The model reproduces it as `TIMESTAMP_NTZ`; a corrected version would land `TIMESTAMP_TZ` (or name the column `created_at_utc`) so consumers cannot read it as Eastern time.
