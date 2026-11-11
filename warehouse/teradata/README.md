# Teradata tooling

Run the root Make targets with Python 3.10+ and Docker Compose v2:

```sh
make sfx-teradata-up NS=sfx-d1110-before ROWS_PER_TABLE=2000 BUSINESS_DATE=20261109
make sfx-teradata-run NS=sfx-d1110-before BUSINESS_DATE=20261109
make sfx-teradata-test NS=sfx-d1110-before
make sfx-teradata-snowconvert NS=sfx-d1110-before SCAI=/path/to/scai
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
`${LANDING_DIR}` and `${BUSINESS_DATE}`. These tokens remain unchanged in conversion
input and must be bound by the execution wrapper after conversion. Output paths
must have an existing parent directory.

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

## SnowConvert

Install SnowConvert AI CLI using the vendor's
[installation instructions](https://docs.snowflake.com/en/en/migrations/snowconvert-docs/general/user-guide/snowconvert/command-line-interface/README).
It is not available on PyPI. The target fails clearly if `scai` cannot be found;
`SCAI=/absolute/path/to/scai` overrides executable discovery.

The target creates `warehouse/teradata/.snowconvert/<UTC timestamp>-<NS>/`.
It copies the DDL/macros/procedures/DBC schema into one-statement `.sql` staging
files and preserves BTEQ `.bteq` files, without modifying the checked-in sources.
After checking that `scai` exists, `bin/snowflake_connection.py` requires
`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`,
`SNOWFLAKE_DATABASE`, and `SNOWFLAKE_PRIVATE_KEY` from the environment. It creates
`~/.snowflake` with mode 700, writes the private key to
`~/.snowflake/sfx_d1110.p8` with mode 600, and updates only `[sfx_d1110]` in
`~/.snowflake/connections.toml` (mode 600), preserving other connections.
The profile uses `SNOWFLAKE_JWT` and an absolute key-file path. Values are never
printed, including in errors. Missing-variable errors contain variable names only.
These files are outside the repository; keep them private and manage their
lifecycle independently of the local PostgreSQL volume. The raw private-key
environment variable is not forwarded to the converter subprocess.

It then runs `scai init <project> -l Teradata`, `scai code add -i <input>
--code-already-split`, captures `scai code convert --help`, then runs
`scai code convert --scripttargetlanguage SnowScript`, with
`SNOWFLAKE_CONNECTION=sfx_d1110`. Source preparation avoids
the arrange phase's SC-tag requirement for unsplit Teradata SQL files.
Flags follow the vendor's
[command reference](https://docs.snowflake.com/en/migrations/aim-for-datawarehouses/manual-migration/SCAI_Command_Reference).

`command.log` records commands, raw stdout/stderr, and exit codes. The entire
project, raw tool output and reports remain under the ignored timestamp directory;
never commit them. No connections are opened by this wrapper, no deployment is
performed, and no credentials are passed as CLI flags. Credentials are written
only to the private files described above, never to the repository or command log.
Actual conversion requires the installed CLI;
the emulator and Make up/run/test targets do not depend on it.
