Staging parity pkg_billing_invoices PASS 376 / 376 differing_keys=0

SQL Server `stg.stg_billing_invoices` vs Snowflake `STAGING.STG_BILLING_INVOICES`, keys invoice_id, line_no, 13 compared columns.

Not compared:
- `extracted_at`: run timestamp: @[System::StartTime] (SQL Server GETDATE() at package start) on SQL Server, query time on Snowflake

The package does not read `BusinessDate` or a watermark (no Script Task, no date filter), so only the 2026-09-30 replay is gated.

### Business decisions

#### line_id lands blank
Explanation: The OLE DB destination maps input column `line_id` to `stg_billing_invoices.line_id`, but no such column exists in the flow: the flat file calls it `id` and no Derived Column renames it. All 376 lines (120 invoices) land `line_id = ''`, so the line-level identifier from legacy billing is lost and the only usable key is (`invoice_id`, `line_no`). The staging model keeps the blank value so parity passes. A correct Snowflake version maps `id` to `line_id`; that is what `--vars '{pkg_billing_invoices_map_line_id: true}'` does. `usp_build_invoice_lines` does not read `line_id`, so `fact_invoice_lines` is not affected either way.

#### issued_at offset stripped, not converted
Explanation: `DER Normalise timestamps` computes `(DT_DBTIMESTAMP2,7)REPLACE(issued_at,"+00","")`. It deletes the literal `+00` suffix and stores a naive `datetime2` that is assumed to be UTC. It does not convert time zones. All 120 invoices (376 lines) in the extract carry `+00`, so no value changes today. An invoice with any other offset would fail the cast, or would be stored at its local wall-clock time if the cast accepted it. The model reproduces this with `to_timestamp_ntz(replace(issued_at, '+00', ''))`. A correct version parses the value as `timestamp_tz` and converts it to UTC explicitly.

#### Lookup no-match behaviour
Explanation: Both Lookups (`LKP Invoice header` on `invoice_id = id`, `LKP Rating period` on `period_id = id`) use the default no-match handling: SSIS fails the component, and the replay passes NULLs that would then be rejected by the NOT NULL columns. In the current data 0 of 376 lines have no invoice and 0 of 120 invoices have no period, so no rows are dropped. The model uses left joins with `not_null` tests on the looked-up columns, so an unmatched line fails the dbt build the same way the package fails. Unmatched lines are never silently filtered out the way an inner join would filter them. A more forgiving Snowflake version would route unmatched lines to an error table and still load the rest.
