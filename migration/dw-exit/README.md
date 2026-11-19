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

## Retirement evidence for sfx1119

UNT4-3 rechecked the 20 proposed retirements in the local `sfx-1119-before`
emulator. The inclusive window is 2026-08-12 through 2026-11-09. The recheck
counts READ usage rows, not returned rows, including setup-day and DBC reads.
Each target is checked under its manifest name and any declared output relation
(a load or ETL artifact is held if its output is still read).

The query ran through the emulator's `bteq.runner.Runner` on the
namespace-derived port. The three bind arrays are the distinct aligned
`(id, db, name)` tuples from those aliases, uppercased and split at the last dot
(empty database for unqualified names).

```sql
WITH aliases AS (
  SELECT * FROM unnest(%s::text[], %s::text[], %s::text[]) AS a(id, db, name)
), reads AS (
  SELECT o.queryid, upper(o.objectdatabasename) AS db, upper(o.objecttablename) AS name
  FROM dbc.qrylogobjectsv o JOIN dbc.qrylogv q USING (queryid)
  WHERE upper(o.usagetype) = 'READ'
    AND q.starttime >= TIMESTAMP '2026-08-12' AND q.starttime < TIMESTAMP '2026-11-10'
)
SELECT a.id, count(r.queryid)
FROM aliases a LEFT JOIN reads r ON a.name = r.name AND (a.db = r.db OR a.db = '')
GROUP BY a.id ORDER BY a.id
```

| Object | READ rows | Disposition |
|---|---:|---|
| `DBC.DBC_QRYLOG` | 2 | Held |
| `DBC.DBC_QRYLOGOBJECTS` | 2 | Held |
| `DBC.DBC_TABLESV` | 2 | Held |
| `DBC.QRYLOGOBJECTSV` | 1 | Held |
| `DBC.QRYLOGV` | 1 | Held |
| `DBC.TABLESV` | 1 | Held |
| `SFX_AUDIT.AUDIT_EVENT_ARCHIVE` | 0 | Retired |
| `SFX_AUDIT.M_ARCHIVE_OVERVIEW` | 0 | Retired |
| `SFX_AUDIT.STG_AUDIT_EVENT_ARCHIVE` | 1 | Held |
| `audit_audit_event_archive` | 1 | Held via staging output |
| `m_SFX_AUDIT_EVENT_ARCHIVE` | 0 | Retired |
| `s_m_SFX_AUDIT_EVENT_ARCHIVE` | 0 | Retired |
| `SFX_DOCUMENTS.SEARCH_INDEX_LOG` | 0 | Retired |
| `SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG` | 1 | Held |
| `SFX_DOCUMENTS.V_SEARCH_HISTORY` | 0 | Retired |
| `documents_search_index_log` | 1 | Held via staging output |
| `SFX_USERS.STG_USER_PREF` | 0 | Retired |
| `SFX_USERS.USER_PREF` | 0 | Retired |
| `SFX_USERS.V_USER_SETTINGS` | 0 | Retired |
| `users_user_pref` | 0 | Retired |

The held entries are still `not_started` and count against
`licence_remaining`. Their reads were from `svc_report_recon` on 2026-08-12.
The board shows 10 retirements (neither green nor red) and 242 remaining
licence dependencies, down from 252. No source objects were removed.

With the BEFORE emulator still running, refresh the board from the existing
manifest with `make sfx-manifest-board-offline RUN_TOKEN=sfx1119`. This
does not reassess or rewrite the manifest and disables the Snowflake
connection even if credentials are set in the shell.

The live `SFX_1119.MIGRATION_CONTROL.OBJECTS` write is deferred until
Snowflake credentials return. The offline test exercises
`parity/promote.py::write_retirements(connection, objects, run_token)`
with a fake connection. It verifies the run-scoped query tag and the upsert
of retired status and retirement reason into `EVIDENCE`.
