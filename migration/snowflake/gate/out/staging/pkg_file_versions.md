Staging parity pkg_file_versions PASS 49999 / 49999 differing_keys=0

SQL Server `stg.stg_file_versions` vs Snowflake `STAGING.STG_FILE_VERSIONS`, keys file_id, version, 4 compared columns.

Not compared:
- `extracted_at`: @[System::StartTime] (GETDATE() of the package run, America/New_York); differs on every run on both sides

### Business decisions

Explanation: The package has no date filter. `SQL Truncate stg_file_versions` empties `stg.stg_file_versions` and `DFT Load stg_file_versions` reloads all of file_versions.csv; the `BusinessDate` parameter is declared but never read. Because the extract is cut at 2026-10-01 23:59:59 UTC, the 2026-09-30 load holds 940 of 49,999 version rows created on 2026-10-01 UTC, 923 of them at exactly 2026-10-01 23:59:59 (the generator clamps a file's last update to the extract time). The 2026-09-15 load holds the same 49,999 rows, 1,206 of them created on or after 2026-09-16. `usp_load_dim_file` filters files by `created_at < @business_date + 1` but counts versions with no date cut, so `dim_file.version_count` includes 924 of these later versions (922 files) for 2026-09-30 and 954 (911 files) for 2026-09-15. The other 16 and 252 belong to files that dim_file leaves out. The model keeps the legacy load (no filter), so parity holds. The alternative is to keep only versions with `created_at < business_date + 1 day`: dbt var `pkg_file_versions_cut_at_business_date` (default `false` = legacy). With it on, the view holds 49,059 rows for 2026-09-30 and 48,793 rows for 2026-09-15. Alternatively, put the same cut in the dim_file model.

Explanation: `DER Normalise timestamps` computes `(DT_DBTIMESTAMP2,7)REPLACE(REPLACE(created_at,"T"," "),"Z","")`. It turns the RFC 3339 UTC string (e.g. `2017-01-06T01:30:49.094Z`) into a zone-less `datetime2` by deleting the `T` and the `Z`, so `created_at` is UTC wall-clock time with no zone, on a server whose clock (and `extracted_at`) is America/New_York. This affects all 49,999 rows on both dates. Nothing is shifted. The model keeps it as `TIMESTAMP_NTZ(7)`. The alternative is to land `TIMESTAMP_TZ`, or rename the column `created_at_utc`, so that consumers can't read it as Eastern time.

### Notes

- `extracted_at` is `@[System::StartTime]`, which the replay takes from SQL Server `GETDATE()`: Eastern wall-clock time (e.g. 2026-10-14 02:30 when UTC was 06:30). The model uses `convert_timezone('America/New_York', current_timestamp())::timestamp_ntz(7)`. A bare `current_timestamp()::timestamp_ntz` would give Los Angeles time (the account session zone), three hours behind. The column is not compared because it changes on every run.
- What was compared: the replay harness (`source/replay/ssis_replay.py`) reads the package XML and evaluates the Derived Column expressions in Python, then BULK INSERTs into `stg`. It doesn't run SSIS. The package has no Script Task, so no C# or Snowpark procedure is involved. Gated on 2026-09-15 and 2026-09-30: `PASS 49999 / 49999` on both, with identical rows, since the package ignores `BusinessDate`.
