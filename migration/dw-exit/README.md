# Warehouse migration

Source inventory, lineage, migration control and parity tooling.

## Local Windows billing close (no remote warehouse)

From the repository root in PowerShell, with Python 3.13 and Docker Desktop:

```powershell
python -m venv warehouse/.venv
python -m venv etl/informatica/.venv
& warehouse/.venv/Scripts/python.exe -m pip install -r migration/dw-exit/billing/requirements-local.txt
& etl/informatica/.venv/Scripts/python.exe -m pip install -r etl/informatica/requirements.txt
$env:NS = 'sfg1120-before'
$env:TD_PG_PORT = (& warehouse/.venv/Scripts/python.exe -c "import zlib; print(54500+zlib.crc32(b'sfg1120-before')%1000)")
docker pull mirror.gcr.io/library/postgres:16
docker tag mirror.gcr.io/library/postgres:16 postgres:16
docker compose -f warehouse/teradata/docker-compose.teradata.yml up -d --wait --pull never
if ($LASTEXITCODE -ne 0) { throw 'Postgres startup failed' }
& warehouse/.venv/Scripts/python.exe migration/dw-exit/billing/local_legacy_close.py --rows 2000 --seed 1110 --business-date 20261109
if ($LASTEXITCODE -ne 0) { throw 'Legacy close failed' }
& warehouse/.venv/Scripts/python.exe migration/dw-exit/billing/duckdb_close.py --landing warehouse/landing --business-date 20261109 --output migration/dw-exit/.runs/duckdb-close
if ($LASTEXITCODE -ne 0) { throw 'DuckDB close failed' }
& warehouse/.venv/Scripts/python.exe migration/dw-exit/billing/close_parity.py --database migration/dw-exit/.runs/duckdb-close/close.duckdb --legacy-exports warehouse/exports --business-date 20261109 --output migration/dw-exit/.runs/duckdb-close
# A mismatch deliberately exits 1; inspect parity.md and parity.json, not just counts.
& warehouse/.venv/Scripts/python.exe -m pytest -q migration/dw-exit/tests/test_duckdb_close.py
```

Leave `RUN_TOKEN` unset (its repository default is used). No remote connector or
remote credentials are installed or used. The compose port is namespace-derived.
The wrapper runs the full BTEQ chain, then all seven billing PowerCenter sessions,
then refreshes storage charges and BTEQ scripts 12/13. PowerCenter updates invoice
totals and appends/replaces journal postings, so running it *after* the final
exports would leave those exports stale. The wrapper supplies the business date
as a PowerCenter parameter override and uses the Windows venv executables.

DuckDB reads the identical landing files directly; it does not copy final billing
results from Postgres. Omit `--landing` to generate a standalone seed with
`--rows 2000 --seed 1110`. It rebuilds only its own `close.duckdb` in `--output`.
`inputs.json` records landing SHA-256s. Storage input is deduplicated as the source
SET table is. The checked-in converted tables, load, storage, monthly procedure
body (run_day is a validated DATE literal), close and views are transpiled using
sqlglot. The four headerless PSV reports and all billing/staging table rows are
written alongside a column/row manifest. Parity reads the live emulator plus the
legacy PSV exports, checks multiplicity-preserving first-column keyed row hashes,
and reports money sums per currency/GL/account in JSON (Markdown is the summary).
Hash comparison ignores trailing ASCII spaces on strings, normalizes numeric
scale and ISO date/timestamp formatting, and preserves case, leading/interior
spaces and NULL versus empty string. The strict hash difference column retains
padding/format differences (numeric scale is still normalized). Money grouping
also ignores trailing spaces. Missing tables/files and SQL failures are fatal.

### Conversion differences are evidence, not a green gate

The supplied conversion is **not equivalent** to the current legacy close. This
runner intentionally does not repair the converted SQL or the planted baseline.
The existing `warehouse/dbt/models/pc/billing` first-load models are rendered
locally into `PC_BILLING`, retained as PSV evidence, and their common columns are
updated into the existing billing targets before close. Older port aliases
`ACCOUNT_NO`/`INVOICE_NO` bind to `ACCOUNT_NUMBER`/`INVOICE_NUMBER`; columns absent
from those older models retain their seeded values. The GL model is materialized
for inspection but the converted monthly procedure subsequently deletes/rebuilds
the entire billing journal. These older dbt models omit fields present in the
current PowerCenter XML (e.g. country/region and invoice tax fields), and differ in
sequence start and GL shape. This is not a full new conversion of the current XML.

Known visible differences include fixed CHAR padding and case-insensitive legacy
joins versus DuckDB VARCHAR comparisons, `40_close.sql`'s elapsed-day PERIOD_KEY
versus the source's YYYYMMDD integer encoding, and converted journal replacement
versus BTEQ's month-scoped rebuild (which retains PowerCenter rows outside the
close month). Thus matching STG counts/hashes is necessary but not sufficient:
the parity command should currently be red. JSON includes sampled before/after
rows and grouped money totals to investigate without suppressing any mismatch.
The existing object-board regression file also runs offline, except its
`test_make_command_line_token_selects_namespace` requires GNU make, which this
Windows environment does not have. No make shim is required by either close.
