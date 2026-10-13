# Playbook: Move one Usage & Billing Warehouse unit from SQL Server to Snowflake, and prove it

> **Facilitator / author:** this file is the source for a **Devin Playbook**.
> Copy its contents into your Devin organization (Settings → Playbooks → *Create
> a new Playbook*) so sessions can invoke it as `!snowflake-migration-unit`.
> See [Creating Playbooks](https://docs.devin.ai/product-guides/creating-playbooks).

## Overview

Use this playbook to move **one unit** of the Usage & Billing Warehouse (UBW) — one T-SQL
procedure from `migration/snowflake/gate/manifest.yaml`, the fact or mart it owns, the package
that feeds it and the SQL Agent / cron step that runs it — from SQL Server to Snowflake. The
estate inventory is `migration/snowflake/INVENTORY.md`; the order units are handed out in is
`migration/snowflake/WAVE-PLAN.md`. Wave one (`usp_rollup_storage_daily` and
`usp_build_mart_tenant_usage`, with their inputs `usp_rollup_usage_events` and
`usp_rollup_audit`) was done with this procedure; the other units follow it.

A unit is done when the parity gate shows it as `PASS`, or as `DIVERGE` with an explanation in
the ledger that says which side is right, why, and which number finance has been looking at.
Nothing on the SQL Server side changes. A legacy number that turns out to be wrong is not
silently corrected: the legacy behaviour stays reachable behind a named dbt var and the data
owners decide.

The repo carries every command and name: `.agents/skills/snowflake-migration/SKILL.md` and the
contract `migration/snowflake/ESTATE.md`. Work happens on `demo-snowflake-migration`; `main` is
not touched.

## Required from user

- **The unit(s)** — procedure names from the manifest, or a wave from `WAVE-PLAN.md`. If the
  message names "the whole warehouse", take the next wave and say so.
- **The run token** as `$UBW_RUN` and the Snowsight URL.
- **Credentials** from organization secrets: `UBW_RUN`, `UBW_DBT_USER`, `UBW_DBT_PRIVATE_KEY`,
  `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_HOST` for the work, `UBW_VIEWER_USER` and
  `UBW_VIEWER_PASSWORD` for the recording. If one is missing, name it and stop. The builder
  token (`SNOWFLAKE_PAT`) is never the answer.

## Procedure

1. **Bring both sides up.** `git checkout demo-snowflake-migration`, then `make sfm-up`
   (about three minutes: SQL Server in Docker, deterministic extracts, the 40 tables, and the
   agent replay for 2026-09-15 and 2026-09-30). Install the target toolchain into a venv from
   `migration/snowflake/target/requirements.txt` and `gate/requirements.txt`, put it first on
   `PATH` and pass `PY=<venv>/bin/python` to every `make sfm-*` target. The run's Snowflake
   database (`OW_UBW_<RUN>`) is already bootstrapped; check with `SHOW SCHEMAS` as the DBT user.
   The gate needs `UBW_SQL_HOST=127.0.0.1 UBW_SQL_PORT=14333 UBW_SQL_USER=sa
   UBW_SQL_PASSWORD=<the compose default> UBW_SQL_DATABASE=OtterWorksUBW` exported; the
   defaults are in `migration/snowflake/compose.yaml` and `source/load.py`.
2. **Read the legacy object before writing anything.** For the unit: the procedure in
   `source/procs/`, the DDL of the table it owns in `source/ddl/`, the package XML in
   `source/ssis/` for each staging table it reads, the reports in `source/reports/` that read
   its table, its step in `source/agent/jobs.yaml` (or `crontab.legacy`), and its manifest
   entry (keys and compare columns). Write down what it reads, what it writes, when it runs and
   every expression that touches dates, money, tier strings or NULLs. Those are where the five
   known differences live (see *Advice*).
3. **Port it in the shape the skill describes.**
   - A staging view per package source it needs in `target/dbt/models/staging/` (`stg_*`,
     materialized as views in `STAGING`, typed and renamed from the quoted lowercase RAW
     columns).
   - One dbt model per procedure in `target/dbt/models/marts/`, named after the procedure with
     `usp_` dropped. Facts and marts that the procedure rebuilds per `@business_date` are
     `incremental` with `incremental_strategy='delete+insert'` and `unique_key='business_date'`,
     and use the `business_date()`, `to_business_date()` and `for_business_date()` macros. The
     output columns are the manifest's keys and compare columns plus `loaded_at`.
   - `schema.yml` tests on every new model: `unique_key_combination` on the manifest keys,
     `not_null` on keys and compare columns, `relationships` to the dims, `accepted_values` on
     tiers; a singular test in `target/dbt/tests/` for any invariant the procedure enforces.
   - A task in `target/tasks/` for the agent/cron step, registered in `TASK_FILES` in
     `tasks.py`, with a `COMMENT` naming the job and step it replaces and
     `TIMEZONE = 'America/New_York'` (the account default is Los Angeles; the legacy server
     clock is Eastern). The model name must be in `MODEL_NAMES`; `tasks.py publish` stages every
     compiled model and wraps incremental ones in a per-date delete/insert.
4. **Load, build, compare — both dates.**
   ```
   make sfm-load-raw RUN=$UBW_RUN PY=$PY
   make sfm-dbt  RUN=$UBW_RUN DATE=2026-09-15 PY=$PY  | tee dbt-build-2026-09-15.log
   make sfm-dbt  RUN=$UBW_RUN DATE=2026-09-30 PY=$PY  | tee dbt-build-2026-09-30.log
   make sfm-gate RUN=$UBW_RUN DATE=2026-09-15 PY=$PY  | tee gate-2026-09-15.log
   make sfm-gate RUN=$UBW_RUN DATE=2026-09-30 PY=$PY  | tee gate-2026-09-30.log
   ```
   Build both dates before gating either; incremental models keep both dates side by side.
5. **Settle every DIVERGE from the data, not from the summary.** Open
   `gate/out/ledger.md`, take a few differing keys and pull the rows behind them from **both**
   databases (SQL Server staging and fact; Snowflake staging and model). Find the expression
   that produces the difference and decide which side is right:
   - Snowflake wrong → fix the model, rebuild, re-gate.
   - Legacy wrong → keep the correct logic as the default and put the legacy expression behind
     a dbt var named for the behaviour (e.g. `legacy_storage_day_eastern_fixed_offset`).
     **Prove the var reproduces the legacy rows**: build the unit with the var on, run
     `gate/parity.py --out <scratch dir>` and keep that output (unit `PASS`); then rebuild
     without it.
   - Write the `Explanation:` line under the unit in `ledger.md`: what differs, which side is
     right and why, the size of the difference on both dates, that finance has been seeing the
     legacy number, and the var that brings it back. The gate carries explanations forward.
6. **Re-run both gates** until every unit of your wave is `PASS` or explained `DIVERGE` and the
   gate line is unchanged on a second run. Units belonging to other waves stay `PENDING`; say
   so — the gate exits 0 only when the whole manifest is ported.
7. **Schedule it.** `make sfm-tasks RUN=$UBW_RUN PY=$PY` then
   `python migration/snowflake/target/tasks/tasks.py --run $UBW_RUN publish`, and
   `EXECUTE TASK OPS.UBW_NIGHTLY_LOAD` once so the graph has run history. Leave the graph
   suspended afterwards. Run `make sfm-gate-test` and `ruff` on anything you touched in
   `target/`.
8. **Open one PR against `demo-snowflake-migration`** with the models, tests, task, ledger
   and whatever the session asked for. The description carries the gate lines for both dates,
   the dbt test count, each DIVERGE in plain words with the named var, and what was compared
   (the replay harness reads the package XML and runs the agent steps in order; it does not run
   SSIS or C#). Do not merge.
9. **Record Snowsight as the READER.** Sign in as `$UBW_VIEWER_USER` (role
   `OW_UBW_<RUN>_READER`, select and monitor only) and record one take: the run's database and
   schemas, the new tables, the task graph and its run history, the query history of the dbt
   build, and `OPS.PARITY_LEDGER`. Attach the recording, the gate logs and the dbt build logs.
10. **Finish** with the gate line, the PR link, the explained divergences and anything that
    blocks cutover.

## Specifications (postconditions)

- `git diff demo-snowflake-migration` touches nothing under `migration/snowflake/source/`,
  `gate/manifest.yaml` or `gate/out/ledger.json` by hand (the gate writes the JSON).
- Every model in the wave has `schema.yml` tests, and `dbt build` for both dates ends with
  `ERROR=0`; the logs are attached to the session.
- Both parity dates show every wave unit as `PASS` or `DIVERGE` with an `Explanation:` line.
- Every kept legacy behaviour has a named var, a proof run with the var on, and a line in the
  PR telling the data owners what they are deciding.
- Every Snowflake object is inside `OW_UBW_<RUN>`; the recording is taken as the READER user.
- A reviewer can re-run `make sfm-gate RUN=$UBW_RUN DATE=2026-09-30` from the PR branch and
  get the same line.

## Worked example: wave one, the storage number

`usp_rollup_storage_daily` buckets hourly storage samples with
`CAST(DATEADD(hour, -4, event_ts_utc) AS date)`. The first gate showed
`rollup_storage_daily DIVERGE 60 / 60, 58 differing keys` on both dates, and
`build_mart_tenant_usage` diverging on `storage_peak_mb` / `bytes_used` only. Pulling one
tenant from both sides: SQL Server's 2026-09-30 peak, 636,141 MB, is a sample taken at
2026-10-01 01:05 UTC — an October sample billed as September. Every other fact in the estate
(usage events, audit, invoices) uses the UTC day, and a fixed −4 h is wrong for every Eastern
standard-time day. Snowflake (UTC day) is right; finance has been seeing the legacy number.
The model keeps `legacy_storage_day_eastern_fixed_offset` (default `false`); with it on, the
gate shows both units `PASS`, which proves the boundary is the only difference. The ledger
says so and the data owners decide whether to switch over at cutover.

## Advice and pointers

- The five known differences: a UTC date boundary in the daily storage rollup (wave 1),
  integer division in per-GB overage proration (wave 2), a NULL archived flag counted as active
  (wave 4), a case-sensitive plan-tier filter (wave 3), and seats counted twice for users in two
  workspaces (wave 3). The first four are legacy defects. The fifth is a source bug the reports
  have always reproduced; the data owners decide whether it survives.
- A unit that reads another unit's table cannot be compared until its input is ported:
  `build_mart_tenant_usage` needed `rollup_usage_events` and `rollup_audit` in the same wave.
  When a mart diverges only in columns copied from a diverging fact, the explanation is the
  fact's.
- `make sfm-dual-run RUN=$UBW_RUN DATE=<date>` replays the legacy load, builds dbt and runs the
  gate in one go. Use it for the nightly check.
- `ACCOUNT_USAGE` lags up to two hours; use `OPS.TASK_HISTORY` and the warehouse query history
  for anything you need to show right away. The X-Small warehouse suspends after sixty seconds;
  the first query is the warm-up.
- The Snowflake account's session time zone is `America/Los_Angeles`. Anything that calls
  `current_date()` (the default business date) must run with `TIMEZONE = 'America/New_York'`.

## Forbidden actions

- Do **not** edit the SQL Server side, the generator, `gate/manifest.yaml` keys or columns, or
  `ledger.json` — however close a unit is to passing.
- Do **not** silently change a finance-facing number. A wrong legacy number stays reachable
  behind a named var and goes to the data owners with the reason in the ledger.
- Do **not** use the builder token; work as the run's `DBT` and `VIEWER` users only.
- Do **not** create Snowflake objects outside the run's database or without the run token in
  their names, and do not create stub tables to turn a `PENDING` unit green.
- Do **not** target `main` or merge the pull request.
