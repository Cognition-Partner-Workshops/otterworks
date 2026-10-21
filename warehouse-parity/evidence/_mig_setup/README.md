# MIG_ schema setup and frozen-window load (plan step s1.2)

Every Snowflake command ran with `WP_SF_SCHEMA_PREFIX=MIG_` from `warehouse-parity/`.
Role `SSP_20261021_DM_ROLE` owns the database, so it could create the schemas without a new grant.

## Steps

1. `python -m wp --dry-run LOG load --engine snowflake` + `board init`, then `python -m wp dry-run-report LOG`:
   `snowflake: 59 statements; schemas in identifier position: MIG_AUDIT, MIG_DW, MIG_PARITY, MIG_STG`.
   The only unprefixed names are inside string literals: the dynamic SQL of the first-pass `usp_build_producer_scorecard`.
2. Wait for a quiet window: `attribute.sessions` must show no statement writing to an unprefixed schema in the last 5 minutes (checked every minute).
3. `python evidence/_mig_setup/snapshot.py before.json`: read-only `information_schema` snapshot of `DW`/`STG`/`AUDIT`/`PARITY`
   (schemata, tables with row_count/bytes/created/last_altered, functions, procedures).
4. `python -m wp load --engine snowflake` runs `first_pass/snowflake/00_ddl.sql` (CREATE SCHEMA MIG_STG/MIG_DW/MIG_AUDIT and
   CREATE OR REPLACE TABLE) **before** it loads the seed, then compiles the first-pass code (`load_snowflake.txt`).
5. `python -m wp board init` creates `MIG_PARITY.BOARD` with the nine manifest objects (`board_init.txt`, `board_show.txt`).
6. `snapshot.py after.json`, then `attribute.py` diffs the two snapshots and lists every Snowflake session in the window
   with the harness schemas its statements name (`isolation.txt`).

The gate of record is **run 3** (no file prefix; `run3_timeline.txt`, 22:22:29–22:23:38 UTC).
Runs 1 and 2 (`run1_*`, `run2_*`) skipped step 2 and overlapped wave activity. They are kept as the record of that overlap.

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

**Run 3: the before/after snapshot of DW/STG/AUDIT/PARITY is IDENTICAL** (`isolation.txt`).
Query history for 22:21:00–22:23:40 UTC shows no statement writing to an unprefixed schema, from any session:

| Session | Statements | Schemas named | Unprefixed writes | Whose |
|---|---:|---|---:|---|
| 4464420937248938 | 4 | - | 0 | this setup: before snapshot |
| 4464420937269462 | 65 | MIG_AUDIT, MIG_DW, MIG_STG | 0 | this setup: `wp load` |
| 4464420937269466 | 12 | MIG_PARITY | 0 | this setup: `wp board init` |
| 4464420937273510, 4464420937212078 | 1 each | MIG_PARITY | 0 | this setup: `wp board show` |
| 4464420937277582 | 4 | - | 0 | this setup: after snapshot |
| 4464420937269458 | 20 | DW, PARITY, STG | 0 | another session, reads only |
| 4464420937248930, 4464420937269454, 4464420937248934 | 3, 1, 1 | PARITY / - | 0 | reads only (quiet-window checks and another session's PARITY read) |
| 4464420937212070, 4464420937224382, 4464420937212074 | 65, 12, 1 | MIG_* | 0 | this setup: aborted attempt `run3a_*`, see below |

**Run 3a (aborted, 22:21:16–22:22:10 UTC):** `snapshot.py` failed on a missing `PYTHONPATH`, so this attempt has no snapshots.
The script still ran the load and board init (`run3a_timeline.txt`, `run3a_load_snowflake.txt`, `run3a_board_init.txt`).
Those statements were all MIG_ (above) and sit inside the attributed window. Run 3 started 19 s later, with the script fixed to stop on the first error.

**Runs 1 and 2: the snapshots are not identical**, and every difference comes from another session:

| Run | This setup's sessions (statements, schemas named) | Unprefixed writes by them | Other sessions writing DW/STG/AUDIT/PARITY in the window |
|---|---|---:|---|
| 1 | snapshot 4464420937248878 (4, -), checks 273454/212006/212010 (1 each, -), load 4464420937273458 (65, MIG_AUDIT/MIG_DW/MIG_STG), board init 4464420937248886 (12, MIG_PARITY), snapshot 4464420937277562 (3, -) | 0 | 4464420937269418: the nightly parity gate, run by hand (an unprefixed `wp load` from 15:00:14 PT that reloads the same frozen seed), plus wave sessions redeploying DW procs/views and updating PARITY.BOARD. The before snapshot started after that load began. |
| 2 | snapshot 4464420937236650 (4, -), load 4464420937224354 (65, MIG_AUDIT/MIG_DW/MIG_STG), board init 4464420937224358 (12, MIG_PARITY), snapshot 4464420937277570 (4, -) | 0 | 4464420937212030 `CREATE OR REPLACE VIEW DW.V_CLAIM_AUDIT`; 4464420937248910 `CREATE OR REPLACE PROCEDURE DW.USP_BUILD_PRODUCER_SCORECARD`; 4464420937248914 `DELETE FROM dw.producer_scorecard` + `CALL dw.usp_build_producer_scorecard` |

All sessions use the same Snowflake user and egress IP. This setup's sessions are identified by the order and shape of their statements, matched against the local timelines.

## Notes for the next step

- First-pass `usp_build_producer_scorecard.sql` did not compile into MIG_DW (`001003 SQL compilation error`, also printed by the loader).
  Its dynamic SQL names `STG.`/`DW.` inside string literals, which the prefix does not remap.
- `00_ddl.sql` is CREATE OR REPLACE: re-running `wp load` or deploying it again wipes MIG_ data, then reloads it.
- Run 3 is the latest load: `mig_counts_snowflake.txt` was re-queried after it (prefix set, so `dw.` resolves to `MIG_DW`).
