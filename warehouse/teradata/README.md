# Teradata tooling

Run the root Make targets with Python 3.10+ and Docker Compose v2:

```sh
make sfx-teradata-up NS=sfx-d1110-before ROWS_PER_TABLE=2000 BUSINESS_DATE=20261109
make sfx-teradata-run NS=sfx-d1110-before BUSINESS_DATE=20261109
make sfx-teradata-test NS=sfx-d1110-before
make sfx-teradata-down NS=sfx-d1110-before
```

`ROWS_PER_TABLE` defaults to 200000, `BUSINESS_DATE` to 20261109. Up creates the
venv, starts PostgreSQL, creates and loads the estate, then executes the chain.
Run executes the chain against existing landing files; test runs `pytest warehouse`;
down removes the namespaced database volume. Data and exports remain gitignored.

## Layout

| Path | Contents |
| --- | --- |
| `ddl/<area>/*.sql` | Databases, core/staging tables, base and layered views |
| `macros/*.sql`, `procedures/*.sql` | Teradata macros and SPL procedures |
| `scripts/<area>/*.bteq` | Core loads, aggregates, billing and reconciliation |
| `load/fastload/*.fl`, `load/tpt/*.tpt` | Staging control files |
| `bteq/`, `bin/bteq` | PostgreSQL-backed BTEQ runtime and CLI shim |
| `jobs/daily_chain`, `jobs/reconcile` | Ordered processing and ad-hoc counts |
| `dbql/` | Deterministic history, catalog, loader and ranking example |
| `../seed/`, `../landing/` | Feed generator/specifications and ignored data |

## Environment and placeholders

`NS` is mandatory. Compose names/volumes contain `sfx-d1110`; its loopback port is
`54500 + crc32(NS) % 1000` unless `TD_PG_PORT` is supplied. Local PostgreSQL uses
trust authentication and is not exposed beyond loopback. Do not use this Compose
configuration for shared or production databases.

The runtime accepts `TD_PG_DSN` or individual `TD_PG_HOST`, `TD_PG_PORT`,
`TD_PG_DB`, `TD_PG_USER`, `TD_PG_PASSWORD`; individual settings override DSN
fields. Defaults: localhost, 5432, teradata, postgres, empty password. Tests need
CREATEDB permission for isolated databases. No credentials belong in source files.
The BTEQ shim uses `warehouse/.venv/bin/python` when available, otherwise
`python3` from PATH (for environments such as CI with dependencies preinstalled).

Source `${VAR}` tokens are runtime substitutions, not SQL syntax. BTEQ uses
environment values or `--var NAME=VALUE`; the chain supplies `BUSINESS_DATE`,
`MONTH_START`, `MONTH_END`, `PERIOD_START_INT`, `PERIOD_END_INT`, and `EXPORT_DIR`.
Dates are `YYYYMMDD`; period integer bounds use the Teradata integer date encoding.
LOGON uses `${TD_HOST}`, `${TD_USER}`, `${TD_PASSWORD}`. Load controls use
`${LANDING_DIR}` and `${BUSINESS_DATE}`. Output paths must have an existing parent
directory.

## Query history

Setup loads `DBC.QryLogV`, `DBC.QryLogObjectsV`, and `DBC.TablesV`. History is
synthetic and deterministic (seed 1110), spanning 2026-08-12 through 2026-11-09,
with denser interactive activity during the final thirty days. To reload and rank:

```sh
export PYTHONPATH=warehouse/teradata TD_PG_PORT=55395
warehouse/.venv/bin/python -m dbql.load
warehouse/teradata/bin/bteq run warehouse/teradata/dbql/consumer_reads.bteq
```

Use the port derived for your NS rather than the example above. The ranking counts
successful SELECT requests per calendar day over the final thirty days; it is not
part of the daily chain. Regenerate CSVs with
`warehouse/.venv/bin/python warehouse/teradata/dbql/generate.py --seed 1110`.
