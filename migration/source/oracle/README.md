# Oracle source estate (Exadata stand-in)

Oracle Free 23ai (`gvenzl/oracle-free:23-slim`) runs as the `oracle-archive` StatefulSet in each
tenant namespace (`infrastructure/helm/oracle-archive`). On the database's first start the image
runs everything in `ddl/` as SYSDBA in name order (`*.sql` via SQL*Plus, `*.sh` as a process), then
`migration/source/seed/oracle.py` loads the SEED-SPEC fixture (1,200,000 / 4,100,000 / 40 rows,
MIG-01..07 planted).

| File | Creates |
|---|---|
| `010_schemas.sql` | users `ARCHIVE` (tables, logic) and `MIGAUDIT` (audit, never migrated) |
| `020`–`040` | `ARCHIVE.RETNPLCY`, `ARCHIVE.DOCARCH`, `ARCHIVE.FILEAUD` (interval-partitioned by `EVENT_TS`) |
| `050_migaudit_purge_audit.sql` | `MIGAUDIT.PURGE_AUDIT` — one row per purged key, written before the delete (CONTRACTS.md §9.4) |
| `060_migaudit_purge_log.sql` | `MIGAUDIT.PURGE_LOG` — autonomous-transaction log of the legacy purge routine |
| `070_archive_retention_pkg.sql` | `ARCHIVE.V_POLICY_LINEAGE`, `ARCHIVE.CLASS_TOTAL_SNAP`, **`ARCHIVE.RETENTION_PKG`** |
| `080_archive_views.sql` | `ARCHIVE.V_ELIGIBLE_DOCS`, `ARCHIVE.V_CLASS_TOTALS`, `ARCHIVE.V_LEGAL_HOLDS` |
| `090_archive_trigger.sql` | `ARCHIVE.SEQ_FILEAUD_TRG`, `ARCHIVE.TRG_DOCARCH_HOLD_AUDIT` |
| `100_archive_scheduler.sql` | `DBMS_SCHEDULER` job `ARCHIVE.NIGHTLY_DISPOSITION` (registered disabled) |
| `110_grants.sh` | object grants + `SELECT_CATALOG_ROLE` for the migration login (`$APP_USER`) |

## The legacy retention logic

The records-retention rules live in the database, as they do on the real estate. The migration
engine's manifest (`selection_sets.closed-7y`, `last_access_before`,
`class_totals.source_class_resolution`) is a hand-transcription of the *selection* subset of these
rules; the package is the system of record.

`ARCHIVE.RETENTION_PKG` (definer rights, owner `ARCHIVE`):

| Member | Rule |
|---|---|
| `RESOLVE_CLASS(code)` | follow `RETNPLCY.SUCCESSOR_CODE` until a code with a blank successor (`F07R -> FIN7`, `L07R -> LGL7`, `H07R -> HRS7`); `-20002` unknown code, `-20003` after 8 hops |
| `RETENTION_YEARS(code)` | years of the *resolved* class |
| `CUTOFF_TS(as_of = 2026-01-01)` | `ADD_MONTHS(TRUNC(as_of, 'YYYY'), -84)` → `2019-01-01 00:00:00` |
| `IN_CLOSED_SCHEDULE(code)` | resolved class ∈ {`FIN7`, `LGL7`, `HRS7`, `TAX7`, `AUD7`} (hard-coded in the package body **and** in `V_POLICY_LINEAGE`) |
| `IS_ELIGIBLE(code, last_access, hold, as_of)` | `0` under legal hold; else `1` iff in schedule and `last_access < CUTOFF_TS` |
| `DISPOSITION_DATE(last_access, code)` | same month/day, year + years; 29 Feb → 28 Feb via `ORA-01839` handler (deliberately **not** `ADD_MONTHS`, which snaps month ends) |
| `NEXT_REVIEW_DATE` | `REVW` (9-year) classes only: disposition date + 6 months |
| `DISPOSITION_DT_TEXT(raw)` | decode `DOCARCH.DISPOSITION_DT` (8 EBCDIC cp037 digits) with `UTL_RAW.CONVERT`; low-values → `NULL`; `-20004` otherwise |
| `DISPOSITION_CODE(...)` | `FILEAUD.DISPOSITION_CODE`: `00` pending, `10` destroy due, `20` review due, `40` legal hold, `90` permanent |
| `CLASS_TOTALS(as_of)` | `SYS_REFCURSOR` of (SOR class, count, `ROUND(SUM(STORAGE_CHARGE), 8)`) over eligible rows |
| `SNAPSHOT_CLASS_TOTALS` | scheduler target, appends to `CLASS_TOTAL_SNAP` |
| `PURGE_ELIGIBLE(run_id, batch, confirm, as_of, OUT purged)` | legacy destruction: audit row, children, parent per key; `ROWNUM`-batched; refuses without `confirm = 'DESTROY ELIGIBLE RECORDS'` (`-20001`); progress via autonomous transaction |

Against the full fixture (as of `2026-01-01`): `V_ELIGIBLE_DOCS` = **180,000** rows (179,963
cohort S + 37 planted), `V_CLASS_TOTALS` per SOR class matches the engine's `class_totals`
(MIG-07: `F07R` rows count toward `FIN7`, `L07R` toward `LGL7`), and `V_LEGAL_HOLDS` only ever holds
cohort O rows (no selected row is under hold).

### Oracle-specific behaviour that does not port 1:1

| Construct | Where | Why it matters when porting |
|---|---|---|
| `CHAR(4)` blank-padded comparison, `RTRIM(...) IS NULL` for "blank" | `RESOLVE_CLASS`, lineage | targets with `VARCHAR` semantics compare `'FIN7'` ≠ `'FIN7 '` |
| `CONNECT BY` / `CONNECT_BY_ROOT` / `SYS_CONNECT_BY_PATH` / `CONNECT_BY_ISLEAF` | `V_POLICY_LINEAGE` | recursive CTE rewrite; `NOCYCLE` semantics |
| PL/SQL function called per row in a view | `V_ELIGIBLE_DOCS` | row-by-row context switch; must become set-based |
| `NVL`, `DECODE`, `ROWNUM` before `ORDER BY` | throughout | `ROWNUM` is applied *before* the sort — the batch is not the smallest keys |
| Package-level associative array initialised in the package body | `g_closed_schedule` | hidden reference data; not visible in any table |
| `SYS_REFCURSOR` return | `CLASS_TOTALS` | table-function / result-set procedure on the target |
| `PRAGMA AUTONOMOUS_TRANSACTION` | `LOG_PURGE` | log survives rollback; no target equivalent inside one transaction |
| `RAISE_APPLICATION_ERROR(-20001..-20004)` | error contract | callers key on the codes |
| `ORA-01839` exception as control flow | `DISPOSITION_DATE` | encode the leap-day rule explicitly |
| `ADD_MONTHS` month-end snapping | `CUTOFF_TS`, `NEXT_REVIEW_DATE` | `DATEADD` keeps the day; equal only because inputs are 1 January / disposition dates |
| `UTL_RAW.CONVERT(... WE8EBCDIC37)` on `RAW(8)` | `DISPOSITION_DT_TEXT`, `V_LEGAL_HOLDS` | code-page conversion of binary columns |
| `NUMBER(31,8)` sums, `ROUND(..., 8)` | class totals | exceeds `DECIMAL(18,8)`; MIG-02 values overflow narrower targets |
| `TIMESTAMP(9)` vs fixture's 12-digit fractions | `LAST_ACCESS_TS` | nanos tail beyond 9 digits already truncated at seed time |
| Row trigger with `:NEW`/`:OLD`, `WHEN` clause, sequence key | `TRG_DOCARCH_HOLD_AUDIT` | no triggers on the target; move to the writer or a stream/task |
| `DBMS_SCHEDULER` job with `repeat_interval` calendar string | `NIGHTLY_DISPOSITION` | target scheduler (task/cron) with different calendar syntax |
| `SELECT_CATALOG_ROLE`, `DBMS_METADATA.GET_DDL` | assessment | how the estate is inventoried |

## Running the estate locally

```bash
docker run -d --name ora-ldm -p 51521:1521 \
  -e ORACLE_PASSWORD=<sys> -e APP_USER=LDM_APP -e APP_USER_PASSWORD=<app> \
  -v "$PWD/migration/source/oracle/ddl:/container-entrypoint-initdb.d:ro" gvenzl/oracle-free:23-slim
# wait for "DATABASE IS READY TO USE!" in `docker logs -f ora-ldm` (2-3 min), then a small fixture:
cd migration/source && ORACLE_PASSWORD=<app> python3 -m seed.oracle --dsn localhost:51521/FREEPDB1 --user LDM_APP --password-env ORACLE_PASSWORD --scale 0.002
```

`seed/test_oracle_retention.py` runs the package against that fixture (skipped without
`LDM_TEST_ORACLE_DSN` / `_USER` / `_PASSWORD`): install order, compile state, `RESOLVE_CLASS`,
`DISPOSITION_DATE` vs the stored EBCDIC `DISPOSITION_DT`, `IS_ELIGIBLE` vs the seed's selection
predicate for every planted key, `V_ELIGIBLE_DOCS` count vs the seed's selected count,
`V_CLASS_TOTALS` vs sums computed from the generator, the trigger, and the purge confirmation guard.
`seed/test_oracle_seed.py` keeps the static checks (file order, `WHENEVER SQLERROR`, grants last).
