# Snowflake migration fixture: the Usage & Billing Warehouse

This folder holds both halves of a warehouse migration. The legacy half is the OtterWorks Usage & Billing Warehouse (UBW) on SQL Server 2022, the way a small data team built it between 2016 and 2019. The target half moves it to Snowflake with dbt and proves parity table by table. `ESTATE.md` is the contract both halves build against; every name in here comes from it.

## The SQL Server side

### Run it

```
make sfm-up      # from the repo root or from this folder
make sfm-down    # stops SQL Server and deletes its volume and the generated extracts
```

`sfm-up` needs Docker and Python 3.12. It prints how long each step took:

1. Starts SQL Server 2022 from `compose.yaml` on `127.0.0.1:14333` and waits for the health check.
2. Runs `source/generate.py`, which writes the CSV extracts to `source/build/extracts/`.
3. Runs `source/load.py`, which creates `OtterWorksUBW`, applies the 40 tables in `source/ddl/` and the 25 procedures in `source/procs/`, loads the agent job catalog into `ops.agent_jobs`, and replays the twelve SSIS packages into `stg`.
4. Runs the `UBW Nightly Load` job through `source/replay/agent_replay.py` for 2026-09-15 and again for 2026-09-30, which fills `dim`, `fact` and `mart`.
5. Prints row counts per table and per schema.

A first run takes a few minutes, most of it the image pull if you don't have it yet. The first run also creates a Python virtualenv in `.venv/`, and later runs reuse it.

To connect yourself, use `sa` with the password from `UBW_SQL_PASSWORD` (the Makefile default is fine for a laptop) on port 14333, database `OtterWorksUBW`. Any of `UBW_SQL_HOST`, `UBW_SQL_PORT`, `UBW_SQL_USER`, `UBW_SQL_PASSWORD` and `UBW_SEED` can be overridden on the make command line.

The legacy server ran on US Eastern time, so the container's clock does too.

### The generated extracts

`source/generate.py` reads the shapes of the services' own schemas: `services/legacy-billing/db/schema.sql`, the auth-service Flyway migrations, the document-service model, the file-service model, the audit-service event, and the analytics-service migration. It pulls column names and allowed values from those files and stops with an error if a column it exports has gone missing, so a schema change in a service shows up here instead of quietly drifting.

It writes one CSV per export with the services' own column names and formats: Postgres-style timestamps from billing, auth, documents and collaboration, RFC 3339 from the file service, .NET round-trip timestamps from the audit service, and epoch nanoseconds from analytics. The seed is `UBW_SEED=20261012`, so two runs with the same seed give byte-identical files. The volumes are the ones in `ESTATE.md`: 60 tenants, about 2,400 users, 180 workspaces, 40,000 documents, 25,000 files, and usage, collaboration, audit and analytics events for 2026-09-01 through 2026-10-01, plus August and September invoices.

### The SSIS packages and the replay

The twelve packages in `source/ssis/` are SSIS package XML as Visual Studio saves it: connection managers, package parameters, an Execute SQL task to clear the staging table, and a Data Flow task with a flat-file source, Derived Column and Lookup transforms, and an OLE DB destination into the matching `stg` table.

SSIS doesn't run on Linux, so `source/replay/ssis_replay.py` does the package's work instead. It parses the `.dtsx`, walks the tasks in precedence order, reads the flat-file source from `source/build/extracts/`, evaluates the Derived Column expressions and Lookups, bulk loads the result into the `stg` table, and writes a row to `ops.etl_run_log` for the package. Three packages, `pkg_billing_usage`, `pkg_files` and `pkg_analytics`, carry a Script Task. The replay harness interprets the documented Script Task intent in Python and never runs C#. The intent is the annotation on the Script Task in the package; the C# body stays in the package as the legacy team wrote it.

Replay one package by hand:

```
.venv/bin/python source/replay/ssis_replay.py pkg_documents
```

### Procedures, jobs and reports

The procedures in `source/procs/` live one per file, and every one that builds a table takes `@business_date date`, deletes that date's rows before it inserts, and logs its start and finish through `dbo.usp_log_run`, so `ops.etl_run_log` shows every package and procedure run with its row counts.

`source/agent/jobs.yaml` is the SQL Agent job catalog: `UBW Nightly Load`, `UBW Hourly Audit`, `UBW Weekly Retention` and `UBW Monthly Overage`, with their steps and schedules. `load.py` copies it into `ops.agent_jobs`, and `agent_replay.py` runs a job's steps in order for a business date you give it, writing one `ops.agent_job_history` row per step the way msdb does:

```
.venv/bin/python source/replay/agent_replay.py --list
.venv/bin/python source/replay/agent_replay.py --job "UBW Monthly Overage" --business-date 2026-09-30
```

`source/agent/crontab.legacy` is the cron side of the schedule, the `etl/` scripts that touch the warehouse. One of them is `etl/scripts/capacity_forecast_weekly.py`, which reads `mart.mart_capacity_forecast_input`, fits a straight-line trend per tenant and writes a 30-day forecast back. It picks its backend from `UBW_BACKEND`; only `sqlserver` works today.

```
UBW_BACKEND=sqlserver .venv/bin/python ../../etl/scripts/capacity_forecast_weekly.py --business-date 2026-09-30
```

The thirty reports in `source/reports/` are SSRS report definitions against `mart` and `fact`. Nothing renders them here. They hold the report-service's queries and parameters, and the migration has to keep those queries giving the same answers. `consumers/consumers.yaml` lists the four readers of the warehouse and what each one reads.

### Tests

```
.venv/bin/pytest source/tests -q
ruff check source ../../etl/scripts/capacity_forecast_weekly.py
```

The tests check that the generator gives identical bytes on two runs and that the replay harness parses all twelve packages. They don't need SQL Server.

## The Snowflake side

### Objects a run creates

A run token like `sfm-20261012-bd` names one Snowflake build. `make sfm-bootstrap RUN=<token>`
runs `target/bootstrap/account.sql` as ACCOUNTADMIN and creates:

- database `OW_UBW_<TOKEN>` with schemas `RAW`, `STAGING`, `MARTS` and `OPS`
- an X-Small warehouse `OW_UBW_<TOKEN>_WH` that suspends after 60 seconds and resumes on use
- a resource monitor `OW_UBW_<TOKEN>_RM`, 5 credits a month, suspending the warehouse at 100
  percent
- role `..._ENGINEER`, which creates tables, views, tasks and procedures inside the
  database and uses the warehouse
- role `..._READER`, which selects from every schema, monitors the warehouse and the `OPS`
  tasks, and nothing else
- service user `..._DBT` with the key pair and default role ENGINEER
- Snowsight user `..._VIEWER` with default role READER, for screen recordings

Every one of those carries the tags `OW_UBW.TAGS.RUN` and `OW_UBW.TAGS.EXPIRES`, except the
resource monitor, which Snowflake doesn't let you tag; teardown and verify-clean find it by
name. The tags live in a small shared `OW_UBW` database that teardown leaves alone. Expiry
defaults to 14 days after the date in the token; pass `EXPIRES=yyyy-mm-dd` for a different
date.
Re-running bootstrap is safe and re-applies the settings.

### Credentials

| Variable | Used by | What it is |
|---|---|---|
| `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_HOST` | everything | account identifier and host |
| `SNOWFLAKE_USER`, `SNOWFLAKE_PAT` | bootstrap, teardown, verify-clean | an ACCOUNTADMIN user and its programmatic access token |
| `SNOWFLAKE_PRIVATE_KEY` | loader, dbt, tasks, gate | PKCS8 PEM for the DBT user; bootstrap derives the public key from it |
| `UBW_VIEWER_PASSWORD` | bootstrap | optional; without it the viewer gets a random password that isn't kept |

### Loading and dbt

`make sfm-load-raw RUN=<token>` puts the same stg CSVs the SSIS replay loaded into an internal
stage and copies them into `RAW`, one table per stg table. `make sfm-dbt RUN=<token>` runs
`dbt build` in `target/dbt/` as the DBT user. The profile reads `UBW_RUN` and the key from
the environment, so there's nothing to edit per run. The project has one model per procedure
with the `usp_` prefix dropped; so far only the seven dimension models exist. Business date
handling lives in `target/dbt/macros/business_date.sql`, and models take the date as the
`business_date` var.

### Tasks

`target/tasks/` replaces the four agent jobs and the forecast cron entry with Snowflake tasks
in `OPS`, rooted at `UBW_NIGHTLY_LOAD`. `make sfm-tasks RUN=<token>` publishes the compiled
dbt models to a stage and creates the tasks suspended, so nothing spends credits until you
resume them with `target/tasks/tasks.py --run <token> resume`.

### Teardown

`make sfm-teardown RUN=<token>` drops everything the run created. `make sfm-verify-clean
RUN=<token>` lists anything that still has the token in its name or in
`SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES` and exits non-zero if anything turns up. That view
can be two hours behind, so a fresh teardown can still show tag rows for a while.

## The parity gate

`gate/manifest.yaml` has one unit per procedure: the procedure, the table it owns on SQL
Server, the dbt model that replaces it, the keys and columns to compare and the business date
column. `make sfm-gate RUN=<token> DATE=<yyyy-mm-dd>` pulls the same keys and columns from
both sides for that date and writes `gate/out/ledger.json` and `gate/out/ledger.md`. The gate
also appends the rows to `OPS.PARITY_LEDGER` so they show up in Snowsight.

Every unit gets one of three statuses: `PASS`, `DIVERGE` or `PENDING`. A divergence lists its first ten differing
keys and the column that differs, plus an `Explanation:` line in `ledger.md` that someone fills
in by hand. Explanations carry over to the next run while the unit still diverges. The gate
prints `Parity PASS=<n> DIVERGE=<n> PENDING=<n>` and exits non-zero while anything is pending
or any divergence is unexplained.

`make sfm-dual-run RUN=<token> DATE=<date>` runs the agent replay on SQL Server and `dbt
build` on Snowflake for the date, then the gate. `make sfm-cutover RUN=<token>` stops the
SQL Server replay, sets `UBW_BACKEND=snowflake` for the consumers and re-reads the last ledger
without connecting to anything. `make sfm-gate-test` runs the comparison unit tests, which use
small in-memory tables and need no connections.

To check the work in Snowsight, log in as the VIEWER user. Query history for the run's
warehouse, task history for the `OPS` tasks and `OPS.PARITY_LEDGER` are all visible under
READER.
||||||| f77dad4aa
