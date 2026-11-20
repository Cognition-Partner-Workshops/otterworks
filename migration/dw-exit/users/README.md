# Users migration — sfg1120

## Scope and safety

Only the 55 manifest objects with `subject_area: users` are covered: **51 conversions
and 4 retirement candidates** (USER_PREF, STG_USER_PREF, users_user_pref, V_USER_SETTINGS).
The initial estimate of 52/3 excludes the dependent view from retirement.

Run scope is `RUN_TOKEN=sfx1120` because the validator requires an sfx prefix;
branch and commit tag is sfg1120. `warehouse/run_config.py env` resolves
`RUN_BEFORE_NAMESPACE=sfx-1120-before`. No validator, source SQL, PowerCenter XML,
Spark job or billing SQL was changed. Step 2 widens target APP_USER/dbt display names
and adds the declared Snowpark APP_USER handler.

Parity is local DuckDB only. Every Snowflake cell is red:
**Snowflake login down; execution disabled**. No Snowflake connection, preflight,
credentials, or live certification was attempted.

## Shipped users SQL and local measurement

- `00_tables.sql`: 18 non-retired tables, source column order/nullability and widths
  except the explicitly approved APP_USER DISPLAY_NAME widening from 60 to 200.
- `10_load.sql`: replacement loads for the users BTEQ chain.
- `20_routines.sql`: P_ACTIVITY_DAILY and M_TEAM_COUNTS resultset.
- `30_views.sql`: V_TEAM_MEMBERS.

The generic local Scripting extractor (`parity/local_sql.py`) and resultset adapter
(`parity/report_outputs.py`) were extracted from the earlier billing harness,
without its billing SQL, report producers, or Spark billing implementations.
`parity/spark_common.py` contains only the schema loader, dbt SELECT renderer,
and column-name adapter needed by users. Billing board measurement remains on its
original `billing/initial` path.

Comparisons preserve row multiplicity, NULLs, exact VARCHAR values and case, with
counts, column profiles, keyed full-row SHA-256 multisets and sampled differences.
The ported DDL-derived semantics ignore only declared CHAR trailing pads, not
VARCHAR suffixes. No truncation, case folding, tolerance, rounding, or new source
normalization was added to clear a mismatch.

## Reproduce locally

From the repository root:

```sh
export RUN_TOKEN=sfx1120
eval "$(warehouse/.venv/bin/python warehouse/run_config.py env)"
export NS="$RUN_BEFORE_NAMESPACE"
make sfx-teradata-up NS="$NS" ROWS_PER_TABLE=200
make sfx-informatica-up NS="$NS" INFA_DB=teradata ROWS_PER_TABLE=200
# informatica-up also seeds the emulator; always specify 200.
PYTHONPATH=.:migration/dw-exit warehouse/.venv/bin/python -m parity.pc_users \
  --capture --dsn 'host=127.0.0.1 port=55380 dbname=teradata user=postgres' \
  --namespace "$NS"
docker pull mirror.gcr.io/library/spark:3.5.3-scala2.12-java17-python3-ubuntu
make sfx-spark-up NS="$NS" ROWS_PER_TABLE=200
for job in team_graph_components user_pref_json_flatten users_active_daily \
           users_login_useragent_parse users_risk_score users_team_rollup; do
  make sfx-spark-run NS="$NS" ROWS_PER_TABLE=200 JOB="$job"
done
make sfx-manifest-board NS="$NS" PARITY_TARGET=duckdb BOARD_ROWS=200
env -u NS warehouse/.venv/bin/python -m pytest -q etl/informatica/tests
warehouse/.venv/bin/python -m pytest -q migration/dw-exit/tests
```

Capture refuses to overwrite its evidence database. Existing evidence lives in
`migration/dw-exit/.runs/pc-users-sessions/`: initial and actual runner tables,
scope/landing/conversion fingerprints, stdout, and checksums. The capture restores
the BTEQ database tables afterward. TEAM_MEMBER is disabled in the source workflow
and therefore is also run as an actual standalone session.

The ordinary capture read/wrote STG_APP_USER 120/120, APP_USER 120/120,
LOGIN_EVENT 200/200, ROLE_GRANT 20/20 and TEAM_MEMBER 40/40.
APP_USER logged 120 updates and zero inserts. Tests additionally cover empty
inputs, merge retention, replacement, router default-route dropping, stale/missing
evidence and conversion errors. A separate router probe and external-consumer
search from the historical run were **not repeated** for this run.

## Step 2: approved widening and local Snowpark proof

Owner decision: **User display names are widened to 200 characters.**
`decisions.json` records scope; the board preserves raw counts/hash differences and
uses `approved_deviation` only after checking every key, name prefix and non-name hash.
Only pre-existing declared CHAR trailing-pad semantics are applied; case folding or
VARCHAR trimming is not permitted. Missing outputs and out-of-scope changes stay red.

`warehouse/snowpark/m_sfx_app_user.py` implements TRANSFORM.M_SFX_APP_USER as a keyed
update/insert merge. `parity/snowpark_users.py` runs it with local_testing=True on the
captured INITIAL.APP_USER and actual PC STG_APP_USER, compares actual runner output
through the DuckDB ladder and records input/handler checksums. The 120 captured rows
all update; synthetic tests additionally cover insert, retention, empty input and
missing-input failure without a live connector. The upstream staging deviation is
validated independently, not hidden by comparing only the already-truncated inputs.
No procedure registration, task deployment or Snowflake execution was attempted.

See [quiet-behaviors.md](quiet-behaviors.md) for all-object semantics and local firing
evidence, and [shared-surfaces.md](shared-surfaces.md) for cross-area readers/writers,
DBQL/registry discrepancies, JDBC side outputs and all 55 manifest owners.
Notably, folder-wide content dbt builds can include disabled TEAM_MEMBER; the
legacy BTEQ and PC login writers disagree outside the all-SUCCESS local fixture.
These audit findings were **not** fixed. JDBC side tables remain unverified.

Current statuses are generated in [board.json](../board/board.json) and
[users-pr.md](../board/users-pr.md); the following Step 1 hold list is historical.

## Step 1 historical results and held differences

Local users board: **45 green / 6 red / 4 retire_verified**.
All 55 Snowflake cells remain red. All migration states remain not_started and
licence counters are unchanged.

| Red object | Before / after | Hash difference | Reason |
|---|---:|---:|---|
| SFX_USERS.APP_USER | 120 / 120 | 200 | 100 display names differ: legacy retains only 60 characters |
| 01_load_users | 140 / 140 | 200 | Same APP_USER mismatch; USER_PROFILE agrees |
| m_SFX_STG_APP_USER | 120 / 120 | 200 | Actual PC target truncates DISPLAY_NAME to 60; shipped dbt retains full values |
| s_m_SFX_STG_APP_USER | 120 / 120 | 200 | Same independently captured PC mapping evidence |
| m_SFX_APP_USER | 120 / 120 | 0 | Held despite isolated PC/dbt agreement on captured PC staging; upstream truncation unresolved |
| s_m_SFX_APP_USER | 120 / 120 | 0 | Same hold; no TRANSFORM.M_SFX_APP_USER Snowpark implementation |

Example key 9000000001:

```text
legacy: Nadia Norford - Senior Workspace Operations and Records Gove
target: Nadia Norford - Senior Workspace Operations and Records Governance Coordinator
```

The zero-diff APP_USER PC proof is conditional on the already-truncated captured
PC staging input. It did not prove end-to-end parity or implement the declared
Snowpark target. Step 2 above adds the handler and independently validates the
upstream owner-approved difference; the raw Step 1 measurements are retained here.

| Actual Spark job | Before / after | Hash difference |
|---|---:|---:|
| team_graph_components | 200 / 200 | 0 |
| user_pref_json_flatten | 200 / 200 | 0 |
| users_active_daily | 7 / 7 | 0 |
| users_login_useragent_parse | 200 / 200 | 0 |
| users_risk_score | 200 / 200 | 0 |
| users_team_rollup | 200 / 200 | 0 |

The six actual jobs use the Spark landing PSV schemas and actual lake Parquet.
Two execute shipped dbt SELECTs locally; four execute extracted shipped Snowpark
Python UDF/UDTF bodies and projections, without connecting to Snowflake.
Manifest dbt_model assignments are not silently changed to Snowpark.
JDBC side outputs and external consumers were not separately checked in this run.

Retirement evidence verifies current checked-out DBQL covering
2026-08-12–2026-11-09, zero reads for USER_PREF and V_USER_SETTINGS, and propagation
to STG_USER_PREF and users_user_pref. Retirement is not migrated parity or cutover
approval. Keep the independent Spark USER_PREF/PREF_JSON landing feed consumed by
user_pref_json_flatten.

See [users-pr.md](../board/users-pr.md) for all 55 object statuses, linked producers
and metric code, and compact counts/hash differences; full profiles and samples
are in [board.json](../board/board.json).
