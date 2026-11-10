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
6. After waves 2 and 3, the orchestrator does wave 4 itself, publishes the models to the Tasks graph and runs the cutover.
7. Close on the final ledger in Snowsight and the session list with its ACU totals.

## Moments to point at

`rate_overage` is the reliable catch. The legacy procedure divides a bigint by an int, which T-SQL truncates to whole gigabytes. A straight port to Snowflake returns fractions, and the gate reported 41 differing tenants on 2026-09-15 (SQL Server `40`, Snowflake `40.638672` for the first one). The worker fixes the model and the unit passes.

`log_run` and `purge_expired` can't pass row for row, because the legacy run log appends a row per replay and per SSIS package. The orchestrator writes an explanation for each in the ledger, and the gate exits 0 only once both explanations are filled in. A person approves the explanations in the PR.

## Fallback

Branch `devin/1794295625-sfm-reference` holds a finished port of all 18 units. On the build run it gave 23 PASS on 2026-09-15 and 2026-09-30, and with the two explanations written, `make sfm-gate` exited 0. If the live run stalls, check that branch out and run `make sfm-dual-run RUN=<token> DATE=2026-09-15`.

## Reset and cleanup

`make sfm-demo-reset RUN=<token>` tears the token down, rebuilds it and brings the ledger back to 7 PASS. Close any worker PRs and delete the run branch. After the demo, run `make sfm-teardown RUN=<token>` and `make sfm-verify-clean RUN=<token>`. The tag check in verify-clean lags by up to two hours, so run it again later in the day.
