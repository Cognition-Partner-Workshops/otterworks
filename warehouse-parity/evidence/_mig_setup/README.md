# MIG_ schema setup and frozen-window load (plan step s1.2)

Every Snowflake command ran with `WP_SF_SCHEMA_PREFIX=MIG_` from `warehouse-parity/`.
Role `SSP_20261021_DM_ROLE` owns the database, so it could create the schemas without a new grant.

## Steps

1. `python -m wp --dry-run LOG load --engine snowflake` + `board init`, then `python -m wp dry-run-report LOG`:
   `snowflake: 59 statements; schemas in identifier position: MIG_AUDIT, MIG_DW, MIG_PARITY, MIG_STG`.
   The only unprefixed names are inside string literals: the dynamic SQL of the first-pass `usp_build_producer_scorecard`.
2. `python evidence/_mig_setup/snapshot.py before.json`: read-only `information_schema` snapshot of `DW`/`STG`/`AUDIT`/`PARITY`
   (schemata, tables with row_count/bytes/created/last_altered, functions, procedures).
3. `python -m wp load --engine snowflake` runs `first_pass/snowflake/00_ddl.sql` (CREATE SCHEMA MIG_STG/MIG_DW/MIG_AUDIT and
   CREATE OR REPLACE TABLE) **before** it loads the seed, then compiles the first-pass code (`load_snowflake.log`).
4. `python -m wp board init` creates `MIG_PARITY.BOARD` with the nine manifest objects (`board_init.log`, `board_show.txt`).
5. `snapshot.py after.json`, then `attribute.py` diffs the two snapshots and lists every Snowflake session in the window
   with the harness schemas its statements name (`isolation.txt`).

Run 1 (`run1_*`, 21:59–22:02 UTC) and run 2 (no `run1_` prefix, 22:03:49–22:04:56 UTC, `run2_timeline.txt`) followed the same steps.
Run 2 repeated the load so the before/after pair is tight around the work.

## Row counts (all ten frozen-window tables)

| Table | Seed CSV | SQL Server `claims_dw` | Snowflake MIG_ |
|---|---:|---:|---:|
| dw.dim_region | 6 | 6 | 6 |
| dw.dim_producer | 60 | 60 | 60 |
| dw.producer_tier | 132 | 132 | 132 |
| dw.dim_policy | 2000 | 2000 | 2000 |
| dw.ClaimStatusRef | 5 | 5 | 5 |
| stg.producer_feed | 204 | 204 | 204 |
| stg.premium_feed | 1500 | 1500 | 1500 |
| stg.claim_feed | 3000 | 3000 | 3000 |
| audit.claim_event | 5000 | 5000 | 5000 |
| audit.policy_event | 3000 | 3000 | 3000 |

Seed = CSV data rows (header excluded). SQL Server = `SELECT COUNT(*)` after `python -m wp legacy-up`.
Snowflake = `SELECT COUNT(*)` against `MIG_DW`/`MIG_STG`/`MIG_AUDIT` (`mig_counts_snowflake.txt`).

## Isolation (g-isolation)

**The snapshot diff is not identical.** The `SSP_20261021_DM` wave kept writing to the unprefixed schemas during both runs.
Query history shows that every change came from a session outside this setup, and that this setup's sessions sent
no statement naming an unprefixed schema in identifier position:

| Run | This setup's sessions (statements, schemas named) | Unprefixed writes by them | Other sessions writing DW/STG/AUDIT/PARITY in the window |
|---|---|---:|---|
| 1 | snapshot 4464420937248878 (4, -), checks 273454/212006/212010 (1 each, -), load 4464420937273458 (65, MIG_AUDIT/MIG_DW/MIG_STG), board init 4464420937248886 (12, MIG_PARITY), snapshot 4464420937277562 (3, -) | 0 | 4464420937269418: an **unprefixed** `wp load` (65 statements from 15:00:14 PT, before this setup's first contact at 15:00:18) that recreated DW/STG/AUDIT tables, plus wave sessions redeploying DW procs/views and updating PARITY.BOARD |
| 2 | snapshot 4464420937236650 (4, -), load 4464420937224354 (65, MIG_AUDIT/MIG_DW/MIG_STG), board init 4464420937224358 (12, MIG_PARITY), snapshot 4464420937277570 (4, -) | 0 | 4464420937248910 `CREATE OR REPLACE PROCEDURE DW.USP_BUILD_PRODUCER_SCORECARD`, 4464420937248914 `DELETE FROM dw.producer_scorecard` + `CALL dw.usp_build_producer_scorecard` |

Run 2 diff, all from 248910/248914: `DW.USP_BUILD_PRODUCER_SCORECARD` recreated, `DW.PRODUCER_SCORECARD` 46 to 0 rows, `DW.ETL_LOG` 9 to 10 rows.
The setup sessions are identified by the order and shape of their statements, matched against the local timeline.
All sessions use the same Snowflake user and egress IP.

## Notes for the next step

- First-pass `usp_build_producer_scorecard.sql` did not compile into MIG_DW (`001003 SQL compilation error`, also printed by the loader).
  Its dynamic SQL names `STG.`/`DW.` inside string literals, which the prefix does not remap.
- `00_ddl.sql` is CREATE OR REPLACE: re-running `wp load` or deploying it again wipes MIG_ data, then reloads it.
