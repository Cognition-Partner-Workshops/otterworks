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

`target/` and `gate/` are built separately against the same `ESTATE.md`; their instructions go here when they land.
