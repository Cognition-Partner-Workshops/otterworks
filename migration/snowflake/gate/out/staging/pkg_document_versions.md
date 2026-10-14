Staging parity pkg_document_versions PASS 100000 / 100000 differing_keys=0

`ssis:pkg_document_versions`: SQL Server `stg.stg_document_versions` vs Snowflake `STAGING.STG_DOCUMENT_VERSIONS`, keys id, 7 compared columns.
Not compared:
- `extracted_at`: @[System::StartTime] of the package run (server clock at load time); differs on every run on both sides

### Notes

What was compared: SQL Server `stg.stg_document_versions` as landed by the replay harness (`source/replay/ssis_replay.py` reads the package XML and evaluates its Derived Column expressions; it does not execute SSIS or C#) against the dbt view `STAGING.STG_DOCUMENT_VERSIONS` over `RAW.EXT_DOCUMENT_VERSIONS` (100,000 rows, same as the CSV). No Lookup, Conditional Split or Script Task, so no Snowpark procedure. `BusinessDate` is declared but never read, so only 2026-09-30 was replayed and gated.

### Business decisions

Explanation: The package ignores its BusinessDate parameter: it truncates `stg.stg_document_versions` and lands every row of `document_versions.csv`, including versions created after the business date. On the 2026-09-30 replay 1,797 of the 100,000 rows have `created_at` on 2026-10-01 (UTC), after the business day closed. `usp_load_dim_document` filters documents by `created_at < business_date + 1` but not their versions, so 1,759 of those 1,797 rows (on 1,748 documents) are counted in `dim_document.version_count` (SQL Server total 99,962; 98,203 with a version date filter); the other 38 belong to documents created on 2026-10-01 and drop out with their document. The staging model keeps this (no date filter) so the row set matches. A corrected Snowflake version would filter `created_at < dateadd(day, 1, var('business_date'))`, either here or in the dim_document model, so a month-end version count only includes versions that existed by that date.

Explanation: The Derived Column `(DT_DBTIMESTAMP2,7)REPLACE(created_at,"+00","")` drops the `+00` UTC offset and stores `created_at` as a `datetime2` with no time zone, on all 100,000 rows. Values do not shift (they are still UTC), but the column no longer says so, and it sits next to `extracted_at`, which uses the server clock in America/New_York. The model reproduces it as `TIMESTAMP_NTZ` in UTC. A corrected version would keep the offset (`TIMESTAMP_TZ`) or name the column `created_at_utc`.
