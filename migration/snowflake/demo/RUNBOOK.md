# SQL Server to Snowflake migration demo runbook

The demo moves the OtterWorks Usage & Billing Warehouse (SQL Server 2022, 25 T-SQL procedures, 12 SSIS packages, SQL Agent jobs and 30 SSRS reports) to Snowflake. Seven dimension procedures are already ported when the demo starts, and Devin ports the other 18 live in parallel sessions while a row-level parity gate checks every one against SQL Server.

## Pre-flight

Do this the day before, on a machine with Docker and the Snowflake secrets.

1. Check out `demo-snowflake-migration` and create a virtualenv from `target/*/requirements.txt` and `gate/requirements.txt`. Pass it to every target as `PY=<venv>/bin/python` and put its `bin` first on `PATH`, so dbt picks up the Snowflake adapter.
2. Export `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_HOST`, `SNOWFLAKE_USER`, `SNOWFLAKE_PAT` and `SNOWFLAKE_PRIVATE_KEY`, plus `UBW_SQL_HOST`, `UBW_SQL_PORT`, `UBW_SQL_USER` and `UBW_SQL_PASSWORD` from the defaults in `migration/snowflake/Makefile`.
3. Run `make sfm-up`. The first pull of the SQL Server image took about 3 minutes on the build machine.
4. Pick a token such as `sfm-20261118-demo` and run `make sfm-demo-reset RUN=<token>`. It took about 3.5 minutes on the build machine, and the last line should read `Parity PASS=7 DIVERGE=0 PENDING=18`. The teardown error at the start is expected when the token is new.
5. Set `UBW_VIEWER_PASSWORD` before the reset if you want to show Snowsight as the read-only `<PREFIX>_VIEWER` user.

## Run

1. Show the legacy side: `migration/snowflake/source/procs/`, an SSIS package in `source/ssis/`, the agent job catalog in `source/agent/jobs.yaml` and `consumers/consumers.yaml` with the 30 reports that read the warehouse.
2. Open the ledger at `gate/out/ledger.md` (or `OPS.PARITY_LEDGER` in Snowsight) showing 7 PASS and 18 PENDING.
3. Start the orchestrator session with `demo/ORCHESTRATOR_PROMPT.md`. It writes the migration plan from `demo/units.yaml` and launches eight wave 1 workers with `demo/CHILD_UNIT_PROMPT.md`.
4. While wave 1 runs, open one worker and walk its trajectory: it reads the procedure, writes the model, runs `make sfm-dual-run` and reads the ledger. On the build machine each dual run took about 100 seconds per date.
5. Open a PR from a worker. The description carries the ledger rows for that unit on both dates.
6. After waves 2 and 3, the orchestrator does wave 4 itself and publishes the models with `tasks.py --run <token> publish`. One execution of the nightly graph (load, dims, facts, marts, log) took about 50 seconds on the build run. Then it runs `make sfm-cutover`, which rechecks the ledger and stops SQL Server only if the gate is clean.
7. Close on the final ledger in Snowsight and the session list with its ACU totals.

## Moments to point at

`rate_overage` is the reliable catch. The legacy procedure divides a bigint by an int, which T-SQL truncates to whole gigabytes. A straight port to Snowflake returns fractions, and the gate reported 41 differing tenants on 2026-09-15 (SQL Server `40`, Snowflake `40.638672` for the first one). The worker fixes the model and the unit passes.

`log_run` and `purge_expired` can't pass row for row, because the legacy run log appends a row per replay and per SSIS package. The orchestrator writes an explanation for each in the ledger, and the gate exits 0 only once both explanations are filled in. A person approves the explanations in the PR.

## Tableau workbook unit

This is the short version of the demo: one BI workflow moves end to end and the parity check is on screen the whole time. The estate has 20 Tableau workbooks in `source/tableau/`, built from 29 of the 30 SSRS reports (`make sfm-bi-workbooks` regenerates them from SQL Server). Each one connects to SQL Server with T-SQL custom SQL. The contract in `gate/bi/workbooks.yaml` lists each workbook's datasources, report, keys and the units behind it.

1. After `make sfm-demo-reset RUN=<token>`, run `make sfm-bi-console` and open `http://127.0.0.1:8050/?live`. All 20 workbooks show as on SQL Server, and the page reloads every 4 seconds.
2. Open `source/tableau/Storage Overage.twb` and point at the three datasources, the `Business Date` parameter and the custom SQL against `mart.mart_overage_charges`.
3. Start one session with `demo/BI_UNIT_PROMPT.md` for `Storage Overage`. It traces the three sheets to `rollup_storage_daily`, `rate_overage` and `build_mart_overage`, ports them and writes `target/tableau/Storage Overage.twb`.
4. When it runs `make sfm-bi-parity`, the Storage Overage page goes red if the first port of `rate_overage` keeps the fractions. On the build run the naive port differed on 41 of 60 tenants on 2026-09-15 (3,699.2481 cents in Snowflake against 3,690 in SQL Server for the top tenant) and on all three plan tiers. Each differing bar and cell is red, with the SQL Server value beside it.
5. The session matches the whole-gigabyte rule, reruns the dual run and the check, and the page turns green on both dates. The datasource cards at the bottom show the T-SQL and the Snowflake SQL side by side.

Snowflake keeps one business date per build, so run `make sfm-dual-run` for a date before `make sfm-bi-parity` for that date. Otherwise every row shows as missing in Snowflake. For the fallback, check out the reference branch and run `python migration/snowflake/demo/apply_reference_workbooks.py --run <token>`, which writes a Snowflake copy of all 20 workbooks. After the dual run for a date, `make sfm-bi-parity RUN=<token> DATE=<date>` showed 20 PASS on both dates on the build run.

## Metabase side by side

The same check as a BI user sees it: one Metabase window on SQL Server and one on Snowflake, with the same cards. `consumers/metabase/dashboards.py` builds each workbook as a Metabase dashboard through the API. Every worksheet becomes one card that runs the datasource's custom SQL with the worksheet's aggregation, sort and mark, so the two dashboards differ only in their connection. The legacy `.twb` goes to the "SQL Server" collection, and the copy in `target/tableau/` goes to the "Snowflake" collection, which connects as the read-only `<PREFIX>_VIEWER` user with the `<PREFIX>_READER` role.

1. With `make sfm-up` running and the run built for the date, run `make sfm-metabase-up`. Metabase starts on `127.0.0.1:3000` and reaches SQL Server as `ubw-sql:1433` on the Compose network.
2. Export `MB_ADMIN_PASSWORD` (the first run creates the admin user with it), the `UBW_SQL_*` values from the pre-flight, `SNOWFLAKE_ACCOUNT` and `UBW_VIEWER_PASSWORD`.
3. Run `make sfm-metabase RUN=<token> DATE=2026-09-30 WORKBOOK="Storage Overage" PY=<venv>/bin/python`. It prints both dashboard URLs. Without `WORKBOOK` it builds all 20 SQL Server dashboards and a Snowflake dashboard for each workbook that has a target copy.
4. Open the two URLs in windows side by side, then run `make sfm-bi-parity RUN=<token> DATE=2026-09-30 WORKBOOK="Storage Overage"` as the proof for every row and value, including the rows off screen.

Reruns update the cards and dashboards in place, so the URLs stay the same. A 1280-pixel window on a 2x screen is only 632 CSS pixels wide, and Metabase drew it in its narrow layout with 10 tenant bars and an "Other" bar. Zoomed out to 67%, both windows showed all 60 tenant bars.

To add a workbook, a worker writes `target/tableau/<workbook>.twb`, gets `make sfm-bi-parity` to PASS for it, then runs `make sfm-metabase RUN=<token> WORKBOOK="<workbook>"`. The Snowflake dashboard appears next to the existing SQL Server one, and nothing else changes.

## Fallback

Branch `devin/1794295625-sfm-reference` holds a finished port of all 18 units. On the build run it gave 23 PASS on 2026-09-15 and 2026-09-30, and with the two explanations written, `make sfm-gate` exited 0. If the live run stalls, check that branch out, run `make sfm-dual-run RUN=<token> DATE=2026-09-15`, then `python migration/snowflake/demo/apply_reference_explanations.py` and `make sfm-gate RUN=<token> DATE=2026-09-15`, which should exit 0.

## Reset and cleanup

`gate/out/` is shared by every token, so a reset also clears explanations written for other runs. `make sfm-demo-reset RUN=<token>` tears the token down, rebuilds it and brings the ledger back to 7 PASS. Close any worker PRs and delete the run branch. The cutover stops the SQL Server container, so run `make sfm-up` before the next rehearsal. After the demo, run `make sfm-teardown RUN=<token>` and `make sfm-verify-clean RUN=<token>`. The tag check in verify-clean lags by up to two hours, so run it again later in the day.
