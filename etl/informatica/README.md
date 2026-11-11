# Emulated PowerCenter estate

PowerCenter 10.5 repository exports for the `sfx-d1110` warehouse plus a Python Integration Service
(`runner/`) that runs them against the emulated Teradata warehouse (PostgreSQL).

## Layout

| Path | Contents |
|---|---|
| `repository/<FOLDER>/mappings/*.XML` | 20 Designer mapping exports (SOURCE, TARGET, TRANSFORMATION, MAPPING, CONNECTOR) |
| `repository/<FOLDER>/wf_*.XML` | Workflow Manager exports with dependencies, one workflow per file: sources, targets, mappings, sessions, worklet and workflow (`wf_SFX_BILLING_DAILY`, `wf_SFX_CONTENT_DAILY`, `wf_SFX_AUDIT_DAILY`) |
| `params/sfx_d1110_daily.par` | parameter file (`$$` mapping parameters, `$DBConnection_*` connection variables) |
| `config/connections.yaml` | relational connection `TD_SFX_EDW`, resolved from `TD_HOST TD_PORT TD_DB TD_USER TD_PASSWORD` |
| `logs/REP_SESS_LOG.psv`, `logs/REP_WFLOW_RUN.psv` | repository run history export (session and workflow runs) |
| `licence.yaml` | licence terms and the mapping-to-feature dependency list |
| `runner/` | the Integration Service and `pmcmd`-style CLI |
| `tests/fixture/` | local fixture: schema (`bootstrap.sql`) and landing files for business date 20261109 |

Folders: `SFX_BILLING` (billing and general ledger), `SFX_CONTENT` (users and documents), `SFX_AUDIT` (audit).

## Run it

```sh
make sfx-informatica-up   NS=sfx-d1110-before   # venv + warehouse database (fixture schema)
make sfx-informatica-run  NS=sfx-d1110-before   # runs the three daily workflows (MAPPINGS=20, i.e. all)
make sfx-informatica-test NS=sfx-d1110-before   # unit + integration tests
make sfx-informatica-down NS=sfx-d1110-before
```

- `INFA_DB=teradata` runs against the Teradata emulation's compose service (`make sfx-teradata-up`) instead of the
  local fixture database. The fixture database listens on `127.0.0.1:55500 + crc32(NS) % 1000`; the Teradata service on
  `54500 + crc32(NS) % 1000`.
- `MAPPINGS` selects what `sfx-informatica-run` executes: `all` or a count `N` (the first N mappings in
  `listobjects` order; 20 or more means all), or comma-separated mapping names or globs, e.g.
  `MAPPINGS=m_SFX_GL_JOURNAL_LINE` or `MAPPINGS='m_SFX_*INVOICE*,m_SFX_PAYMENT'`. Sessions of unselected mappings are
  logged as skipped and their links still fire; a workflow with no selected mapping is not started, and one whose selected
  mappings are all on disabled sessions is not started and exits with an error. `INFA_WORKFLOWS`
  narrows the workflow list (`FOLDER:workflow ...`). The runner reads the same selection from `-mappings` or `$MAPPINGS`.
- Against the seeded warehouse: `make sfx-teradata-up NS=...` then
  `make sfx-informatica-run NS=... INFA_DB=teradata` (source and target columns match `warehouse/seed/columns.py`).
- `LANDING_DIR` overrides the landing zone. It defaults to `warehouse/landing` when that has been generated, else to
  `tests/fixture/landing`. Files are read from `$PMSourceFileDir/<area>/<TABLE>/$$LOAD_DATE.psv`.
- Session logs, workflow logs, reject files, sequence state and the appended `REP_SESS_LOG.psv` are written under
  `infa_shared/<NS>/` (`PMROOTDIR`).

## pmcmd

```sh
cd etl/informatica
python -m runner startworkflow -f SFX_BILLING wf_SFX_BILLING_DAILY
python -m runner startworkflow -f SFX_AUDIT -paramfile /path/override.par wf_SFX_AUDIT_DAILY
python -m runner startsession  -f SFX_BILLING -w wf_SFX_BILLING_DAILY s_m_SFX_PAYMENT
python -m runner listobjects   -f SFX_CONTENT
```

`-sv`, `-d`, `-u`, `-p` are accepted for compatibility and ignored. The exit code is 0 when the workflow succeeds.
`INFA_MAX_SESSIONS` (default 4) caps the sessions that run at the same time.

## Runner semantics

- Transformations: Source Qualifier (source filter, SQL override, sorted ports, distinct), Expression (variable
  ports, default values), Filter, Lookup (connected and `:LKP` unconnected, cached, `Use First Value` / `Use Last Value` /
  `Report Error`), Aggregator, Router (user groups plus `DEFAULT`), Update Strategy (`DD_INSERT`, `DD_UPDATE`,
  `DD_DELETE`, `DD_REJECT`, forward rejected rows) and Sequence Generator (state kept between runs).
- Expressions follow PowerCenter null handling: a NULL condition is false in `IIF`/`DECODE(TRUE, …)`/Filter/Router,
  two-argument `IIF` returns 0, empty string or NULL by type, `||` treats NULL as empty, `NVL`, `ISNULL`, `LTRIM`,
  `RTRIM`, `TO_DATE`, `ADD_TO_DATE`, `DECODE` and the usual string, date and numeric functions.
- Writers honour `Treat source rows as`, `Insert`, `Update as Update`, `Update else Insert`, `Truncate target table
  option`, `Pre SQL` and write rejected rows to `$PMBadFileDir`. CHAR values read from the database lose trailing pad
  blanks.
- Workflows run Start, Session, Worklet, Decision and Email tasks along `WORKFLOWLINK` conditions
  (`$task.Status`, `$task.TgtFailedRows`, `$decision.Condition`). Each session logs target row counts before and after the
  load; a load that only appended rows on top of existing data is flagged as `WRT_8170`.

## SnowConvert

```sh
make sfx-informatica-snowconvert NS=sfx-d1110-before [SNOWFLAKE_CONNECTION=<name>]
```

Runs SnowConvert AI (`scai init -l Teradata`, `scai code add`, `scai code convert`) on the `wf_*.XML` workflow
exports, which satisfy `scai code add`'s one-workflow-per-file check. `scai` reads the Snowflake password only from
`connections.toml`. The untouched output is copied to `snowconvert/<NS>/raw-output/` (git-ignored) with
`init.log`, `add.log` and `convert.log`. Install `scai` with
`curl -fsSL https://snowconvert.snowflake.com/storage/linux/prod/cli/install.sh | sh`.

## Tests

`python -m pytest -q tests` from this directory. Integration tests create a fresh database on the server given by
`TD_*`; when none is reachable and `TD_PORT` is unset they start a throwaway `postgres:16` container.
