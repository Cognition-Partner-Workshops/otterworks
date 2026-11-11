# Playbook: Migrate a SQL Server BI workflow to Snowflake and prove it side by side

> **Facilitator / author:** this file is the source for a **Devin Playbook**.
> Copy its contents into your Devin organization (Settings > Playbooks > *Create
> a new Playbook*) so sessions can invoke it as `!sql_server_to_snowflake_bi`.
> See [Creating Playbooks](https://docs.devin.ai/product-guides/creating-playbooks).

## Overview

This playbook moves one downstream report from a SQL Server warehouse to Snowflake, end to end, and shows the result the way a business user would judge it: the same dashboard open twice, side by side, one window on SQL Server and one on Snowflake, with identical numbers. A row-level check backs the visual by comparing every value, including the ones off screen. Once one report has passed, the same steps fan out to the rest of the BI estate, one session per dashboard.

The fixture is the OtterWorks Usage & Billing Warehouse under `migration/snowflake/` in `Cognition-Partner-Workshops/otterworks`: SQL Server 2022 with 25 T-SQL procedures, SSIS packages, SQL Agent jobs, 20 Tableau workbooks with T-SQL custom SQL, and a dbt project on Snowflake. Metabase renders both sides, because it runs locally and has both drivers built in.

The rule that makes the demo honest: **the legacy SQL Server output is the answer key.** A difference is fixed in the dbt model or the Snowflake SQL. The legacy procedures, the workbooks, the contract in `gate/bi/workbooks.yaml` and the comparison code stay as they are.

## Required from user

- The workbook to migrate. The default is `Storage Overage`: three cards over three procedures, including the T-SQL integer-division rule that a naive port gets wrong.
- **The run token**, such as `sfm-20261118-demo`. Snowflake objects for the run live in `OW_UBW_<TOKEN>` with its own warehouse and roles.
- **Whether to fan out**, and to how many workbooks. Ask before starting more than one worker session.
- Secrets already in the org: `SNOWFLAKE_PAT`, `SNOWFLAKE_PRIVATE_KEY` and `UBW_VIEWER_PASSWORD`. `SNOWFLAKE_USER` is `SMITCHESCOGNITION`. The account is `yd76133.us-east-2.aws`.

## Procedure

1. Check out the latest Snowflake migration branch (the Metabase parity branch, or the run branch the user names). Read `migration/snowflake/AGENTS.md`, `.agents/skills/snowflake-migration/SKILL.md` and `.agents/skills/metabase-bi-parity/SKILL.md`, then build a venv from `migration/snowflake/target/*/requirements.txt` and `gate/requirements.txt` and pass it as `PY=<venv>/bin/python` to every target, with its `bin` first on `PATH`.
2. Bring up the legacy side and the run from the repo root: `make sfm-up`, then `make sfm-demo-reset RUN=<token>`. The reset ends at 7 PASS and 18 PENDING, and creates the read-only Snowsight user `OW_UBW_<TOKEN>_VIEWER` with the password from `UBW_VIEWER_PASSWORD`.
3. Map the workbook before writing anything. Open `source/tableau/<workbook>.twb` and its entry in `gate/bi/workbooks.yaml`, trace each datasource to its SSRS report in `source/reports/` and to the procedures in `source/procs/`, and post the lineage as a short table.
4. Port each unit in the workbook's `units` list that the ledger doesn't show as PASS, to `target/dbt/models/marts/<unit>.sql`. Preserve T-SQL semantics: integer division and `CAST(decimal AS int)` truncate, so use `TRUNC` in Snowflake.
5. Prove the units on both dates with `make sfm-dual-run RUN=<token> DATE=2026-09-15` and `DATE=2026-09-30`. Snowflake holds one business date per build, so always run the dual run for a date before any BI check for that date.
6. Write `target/tableau/<workbook>.twb` as described in `target/tableau/README.md`: same filename, datasource captions, sheets and dashboard, with a Snowflake connection scoped to the run and the custom SQL rewritten against the dbt models. Then run `make sfm-bi-parity RUN=<token> DATE=<date> WORKBOOK="<workbook>"` after each dual run, and fix the model or SQL until every datasource is PASS on both dates.
7. Build the BI side: `make sfm-metabase-up`, then `make sfm-metabase RUN=<token> WORKBOOK="<workbook>"`. This creates the SQL Server dashboard in the "SQL Server" collection and the Snowflake copy in the "Snowflake" collection, with the Snowflake connection running as the viewer user.
8. Record the side by side. Open the two dashboards in two windows (SQL Server left, Snowflake right) at the same business date, zoom out until no chart folds bars into "Other" (67% on a double-scale screen), and scroll through every card. End on the `make sfm-bi-parity` PASS output. Take a full screenshot of each step.
9. Show the data in Snowflake itself: log into Snowsight as the viewer and query the mart and `OPS.PARITY_LEDGER`, so the audience sees the numbers are in Snowflake and not only in Metabase.
10. If the user asked for a fan-out, start one worker per remaining workbook with `demo/BI_UNIT_PROMPT.md`. Use a dynamic workflow for five or more. Each worker gets its own run token, so dual runs for different dates don't overwrite each other. As each PR merges into the run branch, rerun `make sfm-metabase RUN=<token> WORKBOOK=all` and `make sfm-bi-parity RUN=<token> DATE=<date>`, and keep the parity console (`make sfm-bi-console`, `?live`) on screen while the Snowflake collection fills in.
11. Validate, then deliver. `make sfm-gate-test` passes, every migrated workbook shows PASS on both dates, and no password appears in any `.twb`, dashboard or log. Open a PR into the run branch with the lineage, the ledger rows, the recording and the screenshots, and don't merge it.

## Specifications

- The two dashboards differ only in their connection: same cards, order, sorting and formatting.
- `make sfm-bi-parity` reports PASS for every datasource of the migrated workbook on 2026-09-15 and 2026-09-30, with SQL Server reachable or a cached legacy result for that date. Missing legacy evidence is PENDING, never PASS.
- The recording shows SQL Server left and Snowflake right, the same business date on both, every card, and the parity PASS.
- Every Snowflake object carries the run token. Tear down any extra run tokens created for workers with `make sfm-teardown` and `make sfm-verify-clean`.
- Validation: rerunning `make sfm-metabase` changes no dashboard IDs and adds no cards, and the parity console counts add up to 20 workbooks.

## Advice and Pointers

- The red moment is reliable only if it's staged. A naive port of `rate_overage` keeps fractional gigabytes, and the check flags 41 of 60 tenants on 2026-09-15 and 51 of 60 on 2026-09-30. A live session may get it right the first time, so commit the naive model as the starting point when the demo needs the red.
- Show impact as a count of affected customers. The naive port only moves the overage total by about $5, which reads as small on screen.
- Retention Summary's "Archived Items" and the two Sensitive Actions sheets return no rows on either date. They match only because both sides are empty, so don't feature them.
- `gate/out/` is shared by every token, so a reset clears explanations written for other runs.
- `log_run` and `purge_expired` can't match row for row because the legacy run log is append-only. They close as DIVERGE with a written explanation that a person approves.
- Fallback: the reference branch has finished ports of every unit, and `demo/apply_reference_workbooks.py --run <token>` writes the Snowflake copy of all 20 workbooks.

## Forbidden Actions

- Don't edit `source/`, `gate/manifest.yaml`, `gate/compare.py`, `gate/parity.py`, `gate/bi/parity.py` or `gate/bi/workbooks.yaml` to make a check pass.
- Don't write an `Explanation:` line for a DIVERGE yourself. Propose it, and a person approves it in the PR.
- Don't print, commit or paste `SNOWFLAKE_PAT`, `SNOWFLAKE_PRIVATE_KEY`, `UBW_DBT_PRIVATE_KEY`, `UBW_SQL_PASSWORD` or `UBW_VIEWER_PASSWORD`, and don't put a password in a `.twb` file.
- Don't merge into `demo-snowflake-migration` or `main`, and don't approve your own PR.
- Don't run `make sfm-cutover` unless the user asks, since it stops SQL Server.
