# Native Windows billing close (local PostgreSQL to DuckDB)

Run sequentially from PowerShell with Docker Desktop in Linux-container mode.
No Snowflake credentials are needed. Neither wrapper opens a Snowflake connection.
The Snowflake leg awaits access to **SFX_1119**.

## One-time setup

Python 3.12 and uv are recommended. Create separate environments, then install:

```powershell
uv python install 3.12
uv venv --python 3.12 warehouse/.venv
uv venv --python 3.12 etl/informatica/.venv
uv pip install --python warehouse/.venv/Scripts/python.exe -r scripts/windows/requirements.txt
uv pip install --python etl/informatica/.venv/Scripts/python.exe -r etl/informatica/requirements.txt
docker pull postgres:16
```

These environments and run artifacts are gitignored. No Make or dbt installation
is needed for this local adapter. The separate Snowflake/dbt environment, if
already provisioned, is not used.

## Run

```powershell
./scripts/windows/close-legacy.ps1
./scripts/windows/close-migrated.ps1
```

Both accept `-Rows` (default 20000) and `-BusinessDate` (default 20261109);
use identical arguments. Seed is always 1110. This is intentionally smaller than
Make's 200000-row default. The local run token defaults to `sfx1119`, independently
of any inherited Snowflake token; an explicit `RUN_TOKEN` can scope local runs.
The migrated subprocess strips inherited `SNOWFLAKE_*` environment variables.

Legacy starts the emulator, resets the local demo GL to prevent prior PC postings
leaking into the next fixture, runs the full BTEQ daily chain, preserves database
`sfx_windows_close_baseline` **before** PC, then runs all seven billing PC sessions
against the same PostgreSQL database. It prints the prior-month close export.
Repeated legacy runs compare every captured billing table's count and SHA-256.
Do not run legacy and migrated concurrently: legacy replaces the local snapshot
and refuses to do so while it has active readers.

## What DuckDB measures

The BTEQ adapter extends the mechanics of
`migration/dw-exit/parity/object_board.py`, reusing its source snapshot, load/view
materialization, and strict profile/duplicate-aware hash comparison unchanged.
An optional Arrow bulk-copy callback avoids slow per-value Python insertion on
Windows; the board's default loader and all comparison rules are unchanged.
The existing board itself only executes load/view SQL, not stored procedures or
dbt models. There is no checked-in dbt-duckdb profile.

* **BTEQ close:** uses the preserved pre-PC PostgreSQL snapshot. It executes the
  checked-in billing load/storage/view SQL, the straight-conversion monthly
  procedure's SQL statements, close updates, macro SELECTs, and converted export
  SELECTs through SQLGlot's Snowflake-to-DuckDB dialect translation.
* **PC models:** uses the same generated landing files as legacy PC. Like
  `warehouse/parity/commands.py::before`, it creates a fresh local PostgreSQL
  database from the PC bootstrap, runs the billing workflow, captures its outputs,
  and drops that database afterwards. It does not reuse the BTEQ-populated targets.
  The JSON records zero initial target counts and landing-file hashes. It renders
  the seven checked-in billing dbt SELECTs as a clean first build, substitutes raw
  local PSV staging for Snowflake stage access, and transpiles SELECTs to DuckDB.
  The GL lookup source uses the bootstrap's actual schema and reference seed.
  No incremental, governance, comment, or Snowflake file-format hooks are executed.
  This is **not** proof of Snowflake incremental idempotence on existing targets.
* **PC comparison:** uses `warehouse/parity/compare.py` unchanged. Column names
  are uppercased, matched by name rather than position, and selected from BEFORE
  using the YAML exclusions and business keys. Extra AFTER columns are allowed;
  missing required BEFORE columns are errors. Source PostgreSQL types control
  fixed-CHAR trailing-space and numeric normalization, just as in the PC harness.
* No candidate SQL, dbt model, comparison normalization, or expected result is
  changed. The adapter does not project away required legacy columns or rename
  business columns to manufacture a match. Unconstrained PostgreSQL numeric view
  outputs retain their actual fractional scale during snapshot loading.

All objects print before/after counts, hash match, and GREEN/RED. Hash is N/A if
the column layouts differ or an output could not execute. A missing output's
count is N/A, not zero. Execution errors are printed and saved with their SQL.
PC comparisons run even if BTEQ is RED. Exit zero means evidence collection
finished, **not** that migration parity passed. Missing prerequisites or invalid
arguments still fail the command.

Close summaries from both sides use the prior calendar month. DuckDB starts
fresh each run; no Snowflake database or warehouse is created, queried, or cleaned
up.

## Evidence

Gitignored `migration/dw-exit/.runs/windows-close-duckdb/` contains:

* `legacy-snapshot.json`: fixture arguments and billing table counts/hashes;
* `billing-duckdb.json`: 20 billing relations/reports, profiles, hashes, sample
  differences, SQL execution errors, and close summaries;
* `pc-duckdb.json`: seven mappings, rendered/transpiled model SQL, counts, and
  errors, plus bootstrap target counts and input-file hashes;
* `pc-legacy-workflow.log`: the fresh PC baseline's workflow/session statuses.

Outputs describe the latest run. Treat RED and unsupported execution as migration
work remaining, not as a portability failure to suppress.

See [PARITY-NOTES.md](PARITY-NOTES.md) for the audited causes of the current REDs,
adapter corrections, and the saved Snowflake-to-DuckDB comparison.
