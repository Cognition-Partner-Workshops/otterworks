# Warehouse tools

Requires Python 3.10 or later and Docker Compose v2.

```sh
python3 -m venv warehouse/.venv
warehouse/.venv/bin/pip install -r warehouse/requirements.txt
docker pull mirror.gcr.io/library/postgres:16
docker tag mirror.gcr.io/library/postgres:16 postgres:16
export NS=sfx-d1110-before
export TD_PG_PORT=$(python3 -c 'import os,zlib; print(54500+zlib.crc32(os.environ["NS"].encode())%1000)')
warehouse/teradata/bin/compose up -d --wait --pull never
warehouse/.venv/bin/python warehouse/seed/generate.py --rows 200000 --seed 1110
export PYTHONPATH=warehouse/teradata
warehouse/.venv/bin/python -m bteq.setup
warehouse/.venv/bin/python -m bteq.load --landing warehouse/landing --business-date 20261109
warehouse/.venv/bin/python warehouse/teradata/jobs/daily_chain --rows 2000
warehouse/.venv/bin/pytest -q warehouse/seed/tests warehouse/teradata/tests
warehouse/teradata/bin/bteq run path/to/script.bteq --var BUSINESS_DATE=20261109
warehouse/teradata/bin/bteq < path/to/script.bteq
warehouse/teradata/bin/compose down -v
```

`NS` is required for Compose. The host port defaults to 54500 plus the namespace's
CRC32 modulo 1000. Export that port for the runner and tests as above. PostgreSQL
is bound only to the loopback interface and uses local trust authentication.

Connections use `TD_PG_DSN` or `TD_PG_HOST`, `TD_PG_PORT`, `TD_PG_DB`,
`TD_PG_USER`, `TD_PG_PASSWORD`. Defaults are localhost, 5432, teradata, postgres,
and an empty password. Explicit individual variables override DSN fields.
Script `${VAR}` references expand from the environment or repeatable `--var K=V`.
Pass credentials through environment variables, not script literals.

`warehouse/teradata/bteq` contains the interpreter, SQL translation, and connection
bootstrap. Metadata lives in `sfx_td`; database names map to PostgreSQL schemas.
The `tests` directory exercises SQL semantics against PostgreSQL 16 and script
parsing. Database tests skip when no server is reachable only if no `TD_PG_*`
variables were provided. An explicitly configured unreachable server fails tests.
Export destinations must have an existing parent directory.

`seed/columns.py` defines landing-file column order and table sizing. The generator
accepts `--rows`, `--seed`, `--out` (default `warehouse/landing`), and
`--business-date` (default `20261109`). Files are headerless pipe-delimited UTF-8
at `<out>/<area>/<TABLE>/<business-date>.psv`.

`bteq.setup` executes the Teradata files in `teradata/ddl`, creating schemas and
tables before views; existing objects are left intact. `bteq.load` parses the
FastLoad files in `teradata/load/fastload` and the TPT jobs in `teradata/load/tpt`.
Each file load truncates and copies its staging table in one transaction. A
failed copy restores the previous contents. The loader accepts `--controls` to
select another control-file root. The integration tests create and drop an
isolated database, so their configured PostgreSQL role needs CREATEDB permission.

`bteq.setup` also creates the macros and SPL procedures. `jobs/daily_chain` runs
setup, feed generation, staging loads, core loads, daily summaries, monthly
storage and invoice processing, and reconciliation. It stops on the first
nonzero exit and prints step timings. Defaults are `--rows 200000 --seed 1110
--business-date 20261109`; use `--reuse-landing` to load existing feed files.
`--landing` and `--exports` select input and report directories. Reports default
to `warehouse/exports`. The close-period date range is the previous calendar
month; the storage report uses the business date's calendar month.

For a single table count comparison after loading:

```sh
warehouse/.venv/bin/python warehouse/teradata/jobs/reconcile \
  --area documents --table STORAGE_USAGE_DAILY --business-date 20261109
```
