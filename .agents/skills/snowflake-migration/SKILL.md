---
name: snowflake-migration
description: Applies when moving the Usage & Billing Warehouse from SQL Server to Snowflake in this repository, running the parity gate, or tearing down a Snowflake run by its token.
---

# Usage & Billing Warehouse to Snowflake

## Scope

Use this when a session ports a warehouse procedure to dbt, runs the parity gate, rehearses
the cutover, or cleans up Snowflake objects for a run token. The contract is
`migration/snowflake/ESTATE.md`; read it before changing anything. Like every fixture here,
the work is additive and never touches `main`.

## Repository map

- SQL Server side, generator and SSIS replay: `migration/snowflake/source/`. Treat it as the
  thing being migrated. Don't edit it to make parity pass.
- Snowflake objects for a run: `migration/snowflake/target/bootstrap/`.
- dbt project: `migration/snowflake/target/dbt/`, one model per procedure with the `usp_`
  prefix dropped.
- Task graph that replaces the agent jobs and the cron entry:
  `migration/snowflake/target/tasks/`, rooted at `UBW_NIGHTLY_LOAD`.
- Parity gate: `migration/snowflake/gate/manifest.yaml`, `parity.py`, `dual_run.py`,
  `cutover.py`.
- Make targets: `migration/snowflake/target.mk`, included from the root `Makefile`.

## Run tokens and names

Every Snowflake object for a run carries the token in its name and in two tags,
`OW_UBW.TAGS.RUN` and `OW_UBW.TAGS.EXPIRES`. Token `sfm-20261012-bd` gives database
`OW_UBW_SFM_20261012_BD` (schemas `RAW`, `STAGING`, `MARTS`, `OPS`), warehouse `..._WH`, roles
`..._ENGINEER` and `..._READER`, users `..._DBT` and `..._VIEWER`, and resource monitor
`..._RM`. The shared `OW_UBW` database only holds the two tags and survives teardown.

## Credentials

- Builder: `SNOWFLAKE_PAT` with `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER` and optionally
  `SNOWFLAKE_HOST`. Only `bootstrap.py` uses it, for `up`, `teardown` and `verify-clean`.
- Everything else (loader, dbt, tasks, gate) logs in as `<PREFIX>_DBT` with the key pair in
  `SNOWFLAKE_PRIVATE_KEY`, or `UBW_DBT_PRIVATE_KEY` where the organization stores it under
  that name. Bootstrap puts the matching public key on that user.
- SQL Server: `UBW_SQL_HOST`, `UBW_SQL_PORT`, `UBW_SQL_USER`, `UBW_SQL_PASSWORD`.
- Snowsight login for recordings: `<PREFIX>_VIEWER`, role READER. Bootstrap takes the password
  from `UBW_VIEWER_PASSWORD`; without it the user gets a random password nobody keeps.

Never print, commit or paste any of these values.

## Commands

All targets take `RUN=<token>`. `sfm-dbt` accepts an optional `DATE=<yyyy-mm-dd>`; the gate and
dual run require it.

| Target | What it does |
|---|---|
| `make sfm-up` / `make sfm-down` | SQL Server side up and down (owned by `source/`) |
| `make sfm-bootstrap RUN=` | create the run's Snowflake objects |
| `make sfm-load-raw RUN=` | export the source staging tables and load them into `RAW` |
| `make sfm-dbt RUN= [DATE=]` | `dbt build` against the run's database |
| `make sfm-tasks RUN=` | create the task graph, suspended |
| `make sfm-gate RUN= DATE=` | run parity and write the ledger |
| `make sfm-gate-test` | unit tests for the comparison logic, no connections |
| `make sfm-dual-run RUN= DATE=` | agent replay, dbt build, then the gate |
| `make sfm-cutover RUN=` | stop the SQL Server replay, set `UBW_BACKEND=snowflake`, re-read the ledger, and resume the task graph if the reread passes |
| `make sfm-teardown RUN=` | drop everything for the token |
| `make sfm-verify-clean RUN=` | list anything still carrying the token, non-zero if anything does |

The parity dates are 2026-09-15 and the month-end 2026-09-30.

## The ledger

`make sfm-gate` writes `migration/snowflake/gate/out/ledger.json` and `ledger.md`, and appends
the same rows to `OPS.PARITY_LEDGER`. Each unit is one of:

- `PASS`: every row matches on every compared column.
- `DIVERGE`: rows differ. The ledger lists the first ten differing keys and the column.
- `PENDING`: the target model doesn't exist yet.

It prints `Parity PASS=<n> DIVERGE=<n> PENDING=<n>` and exits non-zero while anything is
`PENDING` or any `DIVERGE` has an empty explanation. Explanations are written by hand, in
the `Explanation:` line under the unit's section in `ledger.md`, and they carry forward to the
next run while the unit still diverges. Write what you found and why the Snowflake answer is
right or why the difference is accepted. Don't edit `ledger.json` by hand, and don't change
the manifest's keys or columns to make a unit pass.

## Replay harness scope

`source/replay/` replays the SSIS packages by reading each package's data flow and the
documented intent of its Script Task, then runs the agent job steps in order. It doesn't run
SSIS or execute C#. It exists so both warehouses load the same extracts for the same date,
which is what makes a row by row comparison fair. It isn't a model of production timing,
volumes or failure behaviour.

## Proving parity and leaving evidence

1. Port a procedure to its dbt model, with `schema.yml` tests on its keys.
2. `make sfm-dual-run RUN=<token> DATE=2026-09-15`, then the same for 2026-09-30.
3. Keep the `dbt build` output with its test results.
4. Fill in an explanation for every `DIVERGE` and re-run `make sfm-gate` until it exits 0.
5. Log in to Snowsight as the VIEWER user (role READER) and show query history for the run's
   warehouse, task history for the `OPS` tasks or the `OPS.TASK_HISTORY` view, and
   `OPS.PARITY_LEDGER`. READER can select and monitor and nothing else, so what it shows
   is what ran.

Hand back the ledger, the dbt output and the Snowsight recording together.

## Tearing down by token

`make sfm-teardown RUN=<token>` suspends the task graph, then drops the database, warehouse,
resource monitor, both users and both roles. `make sfm-verify-clean RUN=<token>` checks by
name and through `SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES`. That view lags by up to two hours,
so right after a teardown trust the name checks and run it again later for the tag check.
Every run has an expiry date in its `EXPIRES` tag; anything past it is safe to tear down.
