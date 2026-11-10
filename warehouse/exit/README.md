# Finance warehouse reader exit — sfx-d1110

Run from the repository root with Python 3.10+. Install
`warehouse/requirements.txt`; live Snowflake additionally needs
`snowflake-connector-python` (including cryptography). No team code is imported.

```
python warehouse/exit/reads.py --since 2026-11-09 --until 2026-11-10
python warehouse/exit/board.py --since 2026-11-09 --until 2026-11-10 --html board.html
python warehouse/exit/decommission.py --since 2026-11-10T12:00:00Z
```

All windows are UTC and half-open, `[since, until)`. `until` defaults to now.
The baseline is successful SELECT requests from 2026-10-11 through 2026-11-09,
not rows returned. Per-day counts are included in text/JSON reads output.
ETL (`svc_etl_*`, `svc_fastload`) is shown but never blocks decommissioning.
Every other unknown account blocks it and is reported as unmanaged. Notebook
aliases are recognized by JupyterLab AppID or notebook ClientID; registry account
matches take precedence. Account names are read from registry/DBQL, never embedded.

Live Teradata uses `TD_PG_DSN` or the emulator's `TD_PG_*` settings.
Use `--csv warehouse/teradata/dbql/qrylog.csv` instead for history offline.
Use `--snowflake-json fixture.json` to avoid Snowflake (a list of lowercase
`query_id,start_time,query_tag,query_type,execution_status` dictionaries; `[]`
means no reads). `--json` renders reads as machine-readable JSON.

Snowflake JWT uses `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_ROLE`,
`SNOWFLAKE_PRIVATE_KEY` (PEM text, never persisted). Database and warehouse are
fixed to `SFX_D1110_AFTER` and `SFX_D1110_OPS_WH`. Reporter sessions carry
`run=sfx-d1110,act=exit,phase=reads|board|decommission`; they cannot count as
consumer reads. Successful SELECTs tagged `act=consumers` are merged by query ID
from ACCOUNT_USAGE and recent INFORMATION_SCHEMA history. ACCOUNT_USAGE can lag;
the recent endpoint is limited to 10,000 records and seven days (a full 10,000-row
response fails closed and asks for a narrower window). For high-volume
cutovers wait for ACCOUNT_USAGE to catch up before interpreting a zero as final.
Errors fail the command rather than producing a misleading zero.

Board uses authenticated `gh api`. `--prs-json fixture.json` accepts a list of
GitHub PR objects (`number,state,merged_at,base.ref,head.ref,head.sha,html_url`)
with `workflow_runs` arrays of GitHub Actions run objects. Only the consumer's
workflow, pull_request event and exact head SHA count; latest attempt wins.
Missing, pending, skipped or failed CI is not green. Merged PRs are Snowflake;
green open PRs are transitioning; otherwise Teradata. HTML is self-contained
and escapes all cells; markdown is printed to stdout.

Emulator requests now append DBQL entries, including failed/rolled-back requests,
using a separate autocommit connection. `.LOGON host/account,password` supplies
the logical account (not the PostgreSQL transport identity); `TD_USER` is fallback.
Set `TD_APP_ID` / `TD_CLIENT_ID` (or `AppID` / `ClientID`) for attribution.
Object extraction uses SQLGlot best-effort and does not expand views/routines.
Reloading `dbql.load` intentionally replaces DBQL history, including live logs.

Tests: `PYTHONPATH=warehouse/teradata warehouse/.venv/bin/python -m pytest -q warehouse`.
The existing warehouse CI job already discovers this directory. Offline exit
tests require no network; emulator tests require PostgreSQL.
