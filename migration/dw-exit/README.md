# Warehouse migration

Source inventory, lineage, migration control and parity tooling.

## Promote a subject area

With the BEFORE emulator and converted targets ready, run
`make sfx-area-promote AREA=<area> NS=<before-namespace>`. The namespace defaults to
the run's BEFORE namespace. `make sfx-billing-promote` selects `billing`.
Set `BOARD_DUCKDB_PATH` to a provisioned DuckDB file with the converted output
relations (for example, `AUDIT.AUDIT_EVENT`); without it, the board uses its
built-in initial billing conversion. Promotion never stages or deploys Snowflake targets.

The command reruns both board legs and writes only objects green on both to
`MIGRATION_CONTROL.OBJECTS` and the manifest. It writes per-object evidence and
refusals to `$PARITY_OUT/migration-control.json`, and exits nonzero when none qualify.
Without Snowflake credentials it does not connect, and even a green DuckDB leg is refused.
The counters describe the selected area: `migrated` counts objects, `licence_remaining`
counts unmigrated licence dependencies, and `migrated_areas` counts only complete areas.

Run promotions serially in a checkout. If Snowflake commits but the local
manifest replacement fails, rerun the same promotion to recheck parity and retry
the idempotent update.
