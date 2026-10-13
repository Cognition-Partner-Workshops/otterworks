Staging parity pkg_billing_usage PASS 240752 / 240752 differing_keys=0

SQL Server `stg.stg_billing_usage_events` vs Snowflake `STAGING.STG_BILLING_USAGE_EVENTS`, keys id, 6 compared columns.

Not compared:
- `extracted_at`: @[System::StartTime] of the load run (server clock); differs on every run by design

Also gated for 2026-09-15 (replay, build and gate with that date): `Staging parity pkg_billing_usage PASS 240752 / 240752 differing_keys=0`.

Script Task `SCR Read usage watermark` is ported to Snowpark procedure `OPS.SSIS_PKG_BILLING_USAGE`; after the 2026-09-30 build `CALL OPS.SSIS_PKG_BILLING_USAGE('2026-09-30')` returns `watermark_value` `2026-10-01T23:59:55.0143340` over 240,752 loaded rows, identical to SQL Server `ops.parity_watermarks.watermark_value` for `pkg_billing_usage`.

### Business decisions

Explanation: Watermark incremental load that never revisits old events. The package does not truncate `stg.stg_billing_usage_events`; it appends only extract rows with `occurred_at` strictly greater than the saved watermark (`MAX(occurred_at)` from the previous load, 1900-01-01 when none) and never updates or de-duplicates rows already loaded. Any event that arrives late, or is corrected, with an `occurred_at` at or below the watermark is silently skipped. In this data the first load wrote all 240,752 events; the 2026-09-15 and 2026-09-30 nightly runs each read 240,752 rows and wrote 0. The dbt model keeps this behaviour (incremental append, `occurred_at > max(occurred_at)` of the existing table). A correct Snowflake version would MERGE on `id` with a look-back window (or rebuild from the full extract) so late and corrected events land.

Explanation: The watermark is not capped at the business date. `SQL Update usage watermark` saves `MAX(occurred_at)` over the whole table, and the data flow loads every newer row in the file, including events after the business day. The 2026-09-30 load took 7,753 events dated 2026-10-01 and moved the watermark to 2026-10-01T23:59:55.0143340. After that, a rerun or backfill for 2026-09-15 loads nothing, even though 124,486 events in the file are after 2026-09-15. The model keeps this behaviour (no business-date filter, same watermark). A correct version would load only up to `business_date + 1 day` and keep the watermark per business date, so reruns and backfills are repeatable.

Explanation: The time zone is handled as text. `DER Normalise timestamps` strips the literal `+00` from `occurred_at` and casts the rest to `datetime2(7)`, treating it as UTC (`event_ts_utc` is a copy). A value with any other offset would either fail the cast or be stored as wall-clock time with no shift. Today this touches 0 rows: all 240,752 values end in `+00`, and microsecond precision is kept. The model does the same `replace(occurred_at, '+00', '')::timestamp_ntz`. A correct version would parse the offset (`to_timestamp_tz`) and convert it to UTC.
