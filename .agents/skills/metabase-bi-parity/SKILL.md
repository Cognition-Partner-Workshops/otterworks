---
name: metabase-bi-parity
description: Applies when showing the SQL Server to Snowflake migration in Metabase, building a Tableau workbook from migration/snowflake as SQL Server and Snowflake dashboards, adding one more migrated workbook to Metabase, or recording the two dashboards side by side with the BI parity PASS.
---

# Metabase side by side for the Snowflake migration

## Scope

Use this when a session needs the BI view of the migration: one Metabase window on SQL Server,
one on Snowflake, the same cards in both. Read `.agents/skills/snowflake-migration/SKILL.md`
and `migration/snowflake/AGENTS.md` first. Their rules hold here too: the legacy workbooks in
`source/tableau/`, `gate/bi/workbooks.yaml` and `gate/bi/parity.py` stay as they are, every
Snowflake object stays inside the run's database, and no password, PAT or key is printed or
committed.

## Repository map

- `migration/snowflake/consumers/metabase/dashboards.py` builds the dashboards through the
  Metabase API. It reads the contract and both `.twb` files, so a new workbook needs no code.
- `source/tableau/<workbook>.twb` becomes a dashboard in the "SQL Server" collection, running
  its T-SQL against `OtterWorksUBW`.
- `target/tableau/<workbook>.twb`, when it exists, becomes the same dashboard in the
  "Snowflake" collection, connected as `<PREFIX>_VIEWER` with role `<PREFIX>_READER`.
- Each worksheet is one card: the datasource SQL with its `ORDER BY` dropped, wrapped in the
  worksheet's aggregation and sort. Bar marks are row charts sorted by the measure, Text marks
  are tables sorted by the dimensions. The Tableau `Business Date` parameter is a dashboard
  filter that defaults to `DATE`, and the layout comes from the Tableau dashboard zones.
- Tests: `consumers/metabase/tests/`, run by `make sfm-gate-test`. They use an in-memory
  Metabase API and need no services.
- Runbook: "Metabase side by side" in `migration/snowflake/demo/RUNBOOK.md`.

## Setup

Run every `make sfm-*` from the repo root, with `PY=<venv>/bin/python` built from
`target/*/requirements.txt` and `gate/requirements.txt`.

1. `make sfm-up` for SQL Server, and make sure the run holds the date in Snowflake (`make
   sfm-dual-run RUN=<token> DATE=<date>`). Don't reset or tear down a run someone handed you.
2. `make sfm-metabase-up` starts `metabase/metabase:v0.50.36` on `127.0.0.1:3000`, in the
   same Compose project as SQL Server, so Metabase reaches it as `ubw-sql:1433`.
3. Export the environment. The root Makefile does not export the `UBW_SQL_*` defaults, so
   read them from `migration/snowflake/Makefile` without echoing the password:

   ```bash
   export UBW_SQL_HOST=127.0.0.1 UBW_SQL_PORT=14333 UBW_SQL_USER=sa
   export UBW_SQL_PASSWORD="$(sed -n 's/^UBW_SQL_PASSWORD ?= //p' migration/snowflake/Makefile)"
   export SNOWFLAKE_ACCOUNT=yd76133.us-east-2.aws
   export SNOWFLAKE_HOST=yd76133.us-east-2.aws.snowflakecomputing.com
   export SNOWFLAKE_USER=SMITCHESCOGNITION
   export MB_ADMIN_PASSWORD=<pick one; the first run creates admin@otterworks.local with it>
   ```

   `UBW_VIEWER_PASSWORD` and `SNOWFLAKE_PAT` are org secrets. If they are not in the shell,
   bind them in the exec `env` as `secret:org:UBW_VIEWER_PASSWORD`. Keep the Metabase admin
   password in a file such as `~/.sfm-mb-admin` so later shells can read it.
4. `make sfm-metabase RUN=<token> DATE=<date> WORKBOOK="<workbook>" PY=<venv>/bin/python`. It
   prints both dashboard URLs. `WORKBOOK=all` or no `WORKBOOK` builds all 20 SQL Server
   dashboards and a Snowflake dashboard for each workbook that has a target copy.

## Verify

- `make sfm-bi-parity RUN=<token> DATE=<date> WORKBOOK="<workbook>" PY=<venv>/bin/python`
  ends with `PASS  <workbook>`. This compares every row and value, including rows the cards
  leave off screen. For Storage Overage on 2026-09-30 it was 60/60, 3/3 and 60/60 rows.
- Run `make sfm-metabase` a second time. It prints the same URLs, and the card count in each
  collection stays the same. Cards and dashboards are matched by name within their collection.
- A card can be empty on both sides when its source SQL returns no rows. Retention Summary's
  "Archived Items" and both Sensitive Actions sheets are empty on 2026-09-15 and 2026-09-30.
  Check the source SQL against SQL Server before treating an empty card as a bug.

## Add one more workbook

1. Write `target/tableau/<workbook>.twb` and the dbt models for its units (the Tableau worker
   rules in `migration/snowflake/AGENTS.md`), and get `make sfm-bi-parity` to PASS for it.
2. `make sfm-metabase RUN=<token> DATE=<date> WORKBOOK="<workbook>"`. The Snowflake dashboard
   appears in the "Snowflake" collection, and the SQL Server dashboard is updated in place.
3. Run it again and check the URLs and card counts didn't change.

## Record the side by side

1. Log Chrome in without typing the password on camera: `scripts/browser.py login` posts to
   `/api/session` and sets the `metabase.SESSION` cookie over CDP (`localhost:29229`). It needs
   `playwright` in any venv (`pip install playwright`; it attaches to the running Chrome, so
   no browser download).
2. `scripts/browser.py open <sql-server-url> <snowflake-url>` opens two windows, then place them
   with `wmctrl -i -r <id> -b remove,maximized_vert,maximized_horz` and
   `wmctrl -i -r <id> -e 0,<x>,0,1280,1856` (left at x=0, right at x=1280 on the 2560x1920
   screen). The heading card and collection breadcrumb on each dashboard are the labels.
3. Zoom both windows to 67% (`ctrl+minus` three times). The display has devicePixelRatio 2, so
   a 1280-pixel window is 632 CSS pixels wide and Metabase draws its narrow layout, with 10
   tenant bars and an "Other (51)" bar. At 67% it uses the desktop layout and shows all 60.
4. Run the parity command in a visible terminal. Export the variables before you start
   recording, and never run `env` or show an expanded export on screen.
5. Zoom the recording into a few bars and table rows on both sides, then end on the PASS line.

## Gotchas

- Metabase folds row-chart bars that don't fit the card into "Other". `dashboards.py` grows
  bar cards with their row count, so leave that sizing alone when changing the layout code.
- Snowflake marts hold only the date of the last dbt build. Run `make sfm-dual-run` for a date
  before showing it, or the Snowflake cards are empty.
- `make sfm-metabase` only needs `UBW_VIEWER_PASSWORD` when at least one selected workbook has
  a target copy.

## Cleanup

`docker compose -f migration/snowflake/compose.yaml --profile metabase down` stops Metabase.
Add `-v` to drop the `metabase-data` volume, which also deletes the admin user, the two
connections and every dashboard. Rerunning `make sfm-metabase` recreates them.
