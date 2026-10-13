# Usage & Billing Warehouse migration fixture

`ESTATE.md` is the contract. `source/` holds the SQL Server side, `target/` holds Snowflake,
and `gate/` decides whether the two agree.

## Snowflake side

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
