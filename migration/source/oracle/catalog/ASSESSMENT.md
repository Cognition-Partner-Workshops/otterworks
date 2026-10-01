# Oracle archive estate: Snowflake port assessment

Scope: everything in schemas `ARCHIVE` and `MIGAUDIT` of the Oracle archive database (`oracle-archive`,
service `FREEPDB1`, Oracle AI Database 26ai Free 23.26.3.0.0) beyond the three migrated tables, assessed
against the split target of `migration/manifests/s30-after.yaml`: PostgreSQL keeps the transactional
control plane (`mig.*`), Snowflake holds `STG.*`, `ARCH.*` and a read-only `MIG.*` mirror
(`migration/target/snowflake/README.md`). Nothing here is target code; it is the plan and the parity
bar that target code has to meet.

Evidence:

- Every file `<OWNER>.<OBJECT_TYPE>.<NAME>.sql` in this directory is `DBMS_METADATA.GET_DDL` output,
  verbatim, pulled read-only (`SET TRANSACTION READ ONLY`, `SELECT_CATALOG_ROLE`) by `extract.py`.
  `INVENTORY.json` is the `DBA_OBJECTS` / `DBA_SCHEDULER_JOBS` / `DBA_TRIGGERS` / `DBA_DEPENDENCIES`
  inventory from the same session, with the SHA-256 of each file.
- "Oracle baseline" values below come from read-only queries against the same database on
  2026-09-30 (no DML, `RETENTION_PKG.PURGE_ELIGIBLE` never called, scheduler job left disabled).
- "Snowflake probe" values come from constant-only queries (no database context, no objects created)
  on account `TOJGONB-SF03144`, Snowflake 10.35.101.
- `migration/source/seed/test_oracle_catalog.py` (CI, no Oracle) fails if the seed DDL
  (`migration/source/oracle/ddl/`) creates an object with no catalog file, a catalog file has no seed
  object, a file no longer matches its inventory hash, or this matrix misses a catalogued object.

## 1. Object counts

`DBA_OBJECTS`, owners `ARCHIVE` and `MIGAUDIT`:

| owner | object_type | objects | catalog files | note |
|---|---|---:|---:|---|
| ARCHIVE | TABLE | 4 | 4 | |
| ARCHIVE | TABLE PARTITION | 18 | 0 | partition clauses are inside the parent `TABLE` DDL |
| ARCHIVE | INDEX | 7 | 7 | 4 PK + 3 secondary |
| ARCHIVE | INDEX PARTITION | 36 | 0 | local-index partitions, inside the parent `INDEX` DDL |
| ARCHIVE | VIEW | 4 | 4 | |
| ARCHIVE | PACKAGE | 1 | 1 | `RETENTION_PKG` spec, 70 source lines |
| ARCHIVE | PACKAGE BODY | 1 | 1 | `RETENTION_PKG` body, 217 source lines |
| ARCHIVE | TRIGGER | 1 | 1 | 22 source lines |
| ARCHIVE | SEQUENCE | 1 | 1 | |
| ARCHIVE | JOB | 1 | 1 | `DBMS_METADATA.GET_DDL('PROCOBJ', ...)` |
| MIGAUDIT | TABLE | 2 | 2 | |
| MIGAUDIT | INDEX | 2 | 2 | |
| MIGAUDIT | SEQUENCE | 1 | 0 | `ISEQ$$_73359`, system-generated for the `PURGE_LOG.LOG_ID` identity; defined by the table DDL |
| (schema) | USER | 2 | 2 | `DBMS_METADATA.GET_DDL('USER', ...)`; the schemas themselves |
| **total** | | **81** | **26** | |

No synonyms, types, functions, procedures, materialized views, database links, or other scheduler
objects (programs, schedules, chains) exist in either schema. Row counts: `RETNPLCY` 40, `DOCARCH`
1,200,000, `FILEAUD` 4,100,000, `CLASS_TOTAL_SNAP` 0, `MIGAUDIT.PURGE_AUDIT` 0, `MIGAUDIT.PURGE_LOG` 0.

## 2. Port matrix

Snowflake target categories are the ones fixed for this assessment: native / rewrite as SQL UDF /
rewrite as Snowpark procedure / view / task / drop because the migration engine owns it. "Snowpark
procedure" means a Snowflake stored procedure; the handler is Snowflake Scripting unless the row says
otherwise. Effort is relative points (1, 2, 3, 5, 8, 13), each including its parity test; 1 is a DDL
line with a count check, 13 needs a design decision before code.

| object | kind | what it does | Oracle-specific constructs found | Snowflake target | risk | effort |
|---|---|---|---|---|---|---|
| `ARCHIVE.ARCHIVE` | USER | Schema that owns the archive records, the retention package, views, trigger and nightly job. | `CREATE USER ... NO AUTHENTICATION` (schema-only account), tablespace quota | native: schema `ARCH` in `OTTERWORKS_LDM_S30_AFTER`, created by `ldm init` / tenant bootstrap | L | 1 |
| `MIGAUDIT.MIGAUDIT` | USER | Schema that holds the source-side purge audit and the package's purge log. | `CREATE USER ... NO AUTHENTICATION`, quota | drop because the migration engine owns it (control plane is PostgreSQL `mig.*`) | L | 1 |
| `ARCHIVE.RETNPLCY` | TABLE | Retention policy register: code, years, disposition action, successor for retired codes. | `CHAR(4)` blank-padded codes, blank `SUCCESSOR_CODE` as "terminal", `TIMESTAMP(9)`, `NUMBER(3)` | native: `ARCH.RETNPLCY` (engine LOAD, `CHAR`->`VARCHAR` padding kept on keys) | M | 2 |
| `ARCHIVE.DOCARCH` | TABLE | One row per archived document version: class, last access, storage charge, owner, disposition date, legal hold. | `TIMESTAMP(9)`, `NUMBER(31,8)`, `RAW(40)`/`RAW(8)` holding EBCDIC 037 bytes, `CHAR(n)` keys, range partitioning | native: `ARCH.DOCARCH` (engine LOAD decodes `RAW` with manifest `encoding`, splits `TIMESTAMP` into `NTZ(6)` + `_NANOS_TAIL`) | H | 5 |
| `ARCHIVE.FILEAUD` | TABLE | Audit trail of events per document (access, hold, release, disposition), child of `DOCARCH`. | interval partitioning `NUMTOYMINTERVAL(1,'YEAR')`, `TIMESTAMP(9)`, FK to `DOCARCH` | native: `ARCH.FILEAUD`; interval partitions become micro-partitions (optional clustering key `(RETENTION_CLASS, EVENT_TS)`) | M | 3 |
| `ARCHIVE.CLASS_TOTAL_SNAP` | TABLE | Nightly history of per-class document counts and charge totals for finance. | `TIMESTAMP(9) DEFAULT SYSTIMESTAMP`, `NUMBER(31,8)`, `NUMBER(12)` | native: new `ARCH.CLASS_TOTAL_SNAP` (`TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP()`, `NUMBER(31,8)`); 0 rows to carry | L | 2 |
| `MIGAUDIT.PURGE_AUDIT` | TABLE | Source-side record of every key deleted from the archive, per run. | `TIMESTAMP DEFAULT SYSTIMESTAMP` | drop because the migration engine owns it: the engine writes it inside the Oracle purge unit of work (`CONTRACTS.md` §9.4.4 3b); the control-plane copy is `mig.purge_audit` in PostgreSQL | L | 1 |
| `MIGAUDIT.PURGE_LOG` | TABLE | Free-text progress/error log written by the package's purge. | `GENERATED ALWAYS AS IDENTITY`, written from an autonomous transaction | drop because the migration engine owns it (`mig.stage_log`, `mig.run_ledger`) | L | 1 |
| `ARCHIVE.V_POLICY_LINEAGE` | VIEW | Resolves every policy code through its successor chain to the system-of-record class and flags the closed 7-year schedule. | `CONNECT BY NOCYCLE PRIOR`, `START WITH`, `CONNECT_BY_ROOT`, `SYS_CONNECT_BY_PATH`, `CONNECT_BY_ISLEAF`, `LEVEL`, `RTRIM(...)` on `CHAR(4)`, hard-coded schedule list | view: `ARCH.V_POLICY_LINEAGE` as a bounded `WITH RECURSIVE` (8 hops, `RETENTION_PKG.c_max_hops`), schedule membership from a reference table | H | 8 |
| `ARCHIVE.V_ELIGIBLE_DOCS` | VIEW | Lists documents currently eligible for disposition with system-of-record class, due date, stored date and action code. | five package functions called per row (`RESOLVE_CLASS`, `DISPOSITION_DATE`, `DISPOSITION_DT_TEXT`, `DISPOSITION_CODE`, `IS_ELIGIBLE`), `RAW` decode per row | view: set-based `ARCH.V_ELIGIBLE_DOCS` joining `V_POLICY_LINEAGE` and `RETNPLCY` (no per-row UDF calls) | H | 8 |
| `ARCHIVE.V_CLASS_TOTALS` | VIEW | Per system-of-record class count, charge total and access-date range of the eligible population. | `NUMBER(31,8)` `ROUND(SUM(),8)`, `CUTOFF_TS()` package call, lineage join | view: `ARCH.V_CLASS_TOTALS` (cutoff from the run's manifest `last_access_before`, not a package default) | M | 3 |
| `ARCHIVE.V_LEGAL_HOLDS` | VIEW | Documents under legal hold with readable owner name, last hold event and audit-event count. | `UTL_RAW.CONVERT(...WE8EBCDIC37)` + `UTL_RAW.CAST_TO_VARCHAR2`, `NVL(...,'?')`, correlated scalar subqueries over `FILEAUD` | view: `ARCH.V_LEGAL_HOLDS` over the decoded `OWNER_NAME`; subqueries become one grouped join | M | 3 |
| `ARCHIVE.RETENTION_PKG` | PACKAGE | Public contract of the retention rules: constants, error codes, function and procedure signatures. | `PLS_INTEGER`/`CONSTANT` package globals, `RAISE_APPLICATION_ERROR` codes -20001..-20004, `SYS_REFCURSOR` return, `OUT` parameter, `DEFAULT` parameter values, `DATE '2026-01-01'` as-of default | rewrite as SQL UDF (pure functions) + reference table `ARCH.RETENTION_SCHEDULE` for constants; error codes kept as Snowflake Scripting `EXCEPTION (-2000n, ...)` where a procedure raises | M | 3 |
| `ARCHIVE.RETENTION_PKG` | PACKAGE BODY | Implements the retention rules (resolve, eligibility, disposition dates/codes, class totals, nightly snapshot) and the destructive purge. | package-state associative array `g_closed_schedule` + init block, `PRAGMA AUTONOMOUS_TRANSACTION`, `PRAGMA EXCEPTION_INIT(-1839)` leap-day fallback, `ADD_MONTHS`, `TRUNC(date,'YYYY')`, `UTL_RAW.CONVERT` EBCDIC, `ROWNUM` before `ORDER BY`, `BULK COLLECT`, `SYS_REFCURSOR`, `NVL`, `SELECT ... INTO` + `NO_DATA_FOUND`, `COMMIT` inside procedures | split per subprogram (section 3): SQL UDF / view / Snowpark procedure; `PURGE_ELIGIBLE` becomes a read-only intent view (section 5) | H | 8 |
| `ARCHIVE.TRG_DOCARCH_HOLD_AUDIT` | TRIGGER | Writes a HOLD/RLSE audit event, with actor, client IP and disposition code, whenever a document's legal hold flips. | row-level `AFTER UPDATE OF ... FOR EACH ROW WHEN (NEW.x <> OLD.x)`, `:NEW`/`:OLD`, `SYS_CONTEXT('USERENV', ...)`, `SYSTIMESTAMP`, `SEQ.NEXTVAL`, `DECODE`, `NVL` | rewrite as Snowpark procedure `ARCH.SET_LEGAL_HOLD` (the only writer of the flag: update + audit insert in one transaction); optional stream + task as a detector for direct updates | H | 13 |
| `ARCHIVE.SEQ_FILEAUD_TRG` | SEQUENCE | Numbers trigger-written audit events (`TRG` + 17-digit counter). | `NOCACHE NOORDER`, `MAXVALUE 9999999999999999999999999999` | native: `ARCH.SEQ_FILEAUD_TRG START WITH <Oracle LAST_NUMBER>` (1 today); Snowflake sequences may leave gaps | L | 1 |
| `ARCHIVE.NIGHTLY_DISPOSITION` | JOB | Nightly 02:00 snapshot of eligible class totals into `CLASS_TOTAL_SNAP` (disabled in production). | `DBMS_SCHEDULER.CREATE_JOB` `PLSQL_BLOCK`, calendar string `FREQ=DAILY; BYHOUR=2; BYMINUTE=0; BYSECOND=0`, `TRUNC(SYSDATE)`, `max_failures=3`, `restartable`, NLS environment | task: `ARCH.NIGHTLY_DISPOSITION` `SCHEDULE = 'USING CRON 0 2 * * * UTC'`, created and left `SUSPENDED`, calling `ARCH.SNAPSHOT_CLASS_TOTALS(CURRENT_DATE())` | M | 3 |
| `ARCHIVE.PK_RETNPLCY` | INDEX | Enforces one row per policy code. | unique B-tree backing the PK | native: informational `PRIMARY KEY`; uniqueness proven by the engine's VALIDATE, not enforced | L | 1 |
| `ARCHIVE.PK_DOCARCH` | INDEX | Enforces one row per archive key. | unique B-tree backing the PK | native: informational `PRIMARY KEY (NAMESPACE, ARCH_KEY)` (already in `080_arch_tables.sql`) | L | 1 |
| `ARCHIVE.PK_FILEAUD` | INDEX | Enforces one row per audit event key. | local partitioned unique index | native: informational `PRIMARY KEY` | L | 1 |
| `ARCHIVE.PK_CLASS_TOTAL_SNAP` | INDEX | Enforces one snapshot row per class per snapshot time. | unique B-tree | native: informational `PRIMARY KEY`; `MERGE` in the snapshot procedure keeps it true | L | 1 |
| `ARCHIVE.IX_DOCARCH_SELECT` | INDEX | Speeds the class + last-access selection used by eligibility and extraction. | composite B-tree `(RETENTION_CLASS, LAST_ACCESS_TS)` | native: no index; micro-partition pruning, optional clustering key if the view is slow | L | 1 |
| `ARCHIVE.IX_FILEAUD_PARENT` | INDEX | Speeds child lookup by document key (holds view, purge). | local partitioned B-tree on `ARCH_KEY` | native: no index | L | 1 |
| `ARCHIVE.IX_FILEAUD_SELECT` | INDEX | Speeds the class + event-time selection of audit rows. | local partitioned B-tree `(RETENTION_CLASS, EVENT_TS)` | native: no index; clustering key candidate | L | 1 |
| `MIGAUDIT.PK_PURGE_AUDIT` | INDEX | One audit row per run, table and key. | unique B-tree | drop because the migration engine owns it (`mig.purge_audit` PK) | L | 1 |
| `MIGAUDIT.PK_PURGE_LOG` | INDEX | One log row per identity value. | unique B-tree | drop because the migration engine owns it | L | 1 |

## 3. `RETENTION_PKG` by subprogram

| subprogram | business rule | Snowflake target | risk | effort |
|---|---|---|---|---|
| `RESOLVE_CLASS(code)` | follow `SUCCESSOR_CODE` until blank; unknown code -20002, more than 8 hops -20003 | view (`V_POLICY_LINEAGE.SOR_CODE`); errors become rows with `SOR_CODE IS NULL` / `HOPS = 8` that VALIDATE rejects | H | 5 |
| `RETENTION_YEARS(code)` | years of the resolved class | view column (join `RETNPLCY` on `SOR_CODE`) | L | 1 |
| `CUTOFF_TS(as_of)` | Jan 1 of `as_of`'s year minus 84 months; default as-of is the constant `DATE '2026-01-01'` | rewrite as SQL UDF `ARCH.CUTOFF_TS(AS_OF DATE)`; callers pass the run's manifest date, never a baked-in default | M | 1 |
| `IN_CLOSED_SCHEDULE(code)` | resolved class is one of `FIN7 LGL7 HRS7 TAX7 AUD7` (package state) | view column from reference table `ARCH.RETENTION_SCHEDULE` | M | 2 |
| `IS_ELIGIBLE(code, ts, hold)` | not on hold, closed schedule, last access before cutoff | view predicate (set-based) | M | 2 |
| `DISPOSITION_DATE(ts, code)` | month/day of last access in year `+ retention_years`; 29 Feb -> 28 Feb | rewrite as SQL UDF using `DATEADD(year, n, ts::DATE)` | H | 3 |
| `NEXT_REVIEW_DATE(ts, code)` | review-class disposition date + 6 months, else NULL | rewrite as SQL UDF using `ADD_MONTHS` | M | 2 |
| `DISPOSITION_DT_TEXT(raw)` | stored EBCDIC `YYYYMMDD`; low-values -> NULL; other bytes -20004 | none in Snowflake: the engine decodes at LOAD (`encoding: cp037`, `format: YYYYMMDD`; low-values -> `DATE_INVALID` reject); view column `TO_CHAR(DISPOSITION_DT, 'YYYYMMDD')` | M | 2 |
| `DISPOSITION_CODE(code, ts, hold, as_of)` | 40 hold, 90 permanent, 00 not yet due, 20 review due, 10 destroy due | rewrite as SQL UDF (scalar `CASE`, no table access) fed by view columns | M | 3 |
| `CLASS_TOTALS(as_of)` | per-class count and `ROUND(SUM(charge), 8)` as a ref cursor | view `ARCH.V_CLASS_TOTALS` (or SQL UDTF `RETURNS TABLE` when a parameterised as-of is needed) | M | 3 |
| `SNAPSHOT_CLASS_TOTALS(as_of)` | append class totals to `CLASS_TOTAL_SNAP`, commit | rewrite as Snowpark procedure (`INSERT ... SELECT` from the view), called by the task | M | 2 |
| `LOG_PURGE` (private) | autonomous-transaction log line | drop because the migration engine owns it | L | 0 |
| `PURGE_ELIGIBLE(run, batch, confirm, as_of, OUT n)` | confirmation phrase, then delete eligible documents and their audit events in `ROWNUM` batches with audit rows | drop because the migration engine owns it; Snowflake gets the read-only intent view of section 5 | H | 5 |

## 4. Non-portable constructs

Each row: where it is, what Oracle actually does (baseline), what it becomes, and the parity test that
has to pass before the Snowflake object is accepted. Parity tests run the same inputs through the
Oracle object (read-only) and the Snowflake object (scratch database `OTTERWORKS_LDM_LDM_CI`) and
compare results exactly.

| construct | where | Oracle behaviour (baseline) | Snowflake | parity test |
|---|---|---|---|---|
| Hierarchical query `CONNECT BY NOCYCLE`, `CONNECT_BY_ISLEAF`, `CONNECT_BY_ROOT`, `SYS_CONNECT_BY_PATH` | `V_POLICY_LINEAGE`; `RESOLVE_CLASS` loop | Leaf rows only; `NOCYCLE` silently stops on a cycle; `F07R -> FIN7`, `L07R -> LGL7`, `H07R -> HRS7` (1 hop each) | Snowflake supports `CONNECT BY` but probe: `CONNECT_BY_ISLEAF` is an invalid identifier, `NOCYCLE` is a syntax error, and a 2-code cycle ran until the 45 s statement timeout. Use `WITH RECURSIVE` bounded at 8 hops with an explicit `HOPS = 8` cycle marker (probe returns the expected `F07R>FIN7`, `L07R>LGL7`, and flags `CYA1>CYB1>...` at 8) | (a) all 40 codes: `(POLICY_CODE, SOR_CODE, HOPS, LINEAGE, IN_CLOSED_SCHEDULE)` identical to Oracle; (b) fixture with a 2-code cycle: Oracle `RESOLVE_CLASS` raises -20003, Snowflake row has `HOPS = 8` and is excluded from eligibility; (c) the lineage (not the manifest `value_map`) is what classifies `F07R`/`L07R`: FIN7 and LGL7 charge sums match Oracle `V_CLASS_TOTALS` to 8 dp |
| `PRAGMA AUTONOMOUS_TRANSACTION` | `LOG_PURGE` | log line commits even when the purge rolls back | no autonomous transactions in Snowflake stored procedures (inference from the transaction docs; not probed). Not needed: the only user is purge, which is not ported; the engine commits `mig.purge_audit` `INTENDED` in PostgreSQL before the source unit of work | test that no Snowflake object references `PURGE_LOG`; engine purge tests already cover the INTENDED-before-delete order |
| `SYS_REFCURSOR` | `CLASS_TOTALS` | caller fetches (class, count, rounded charge) | view `ARCH.V_CLASS_TOTALS` (or `RETURNS TABLE` UDTF) | 5 closed classes: counts `AUD7 35,760 / FIN7 35,880 / HRS7 35,783 / LGL7 36,125 / TAX7 36,452` and charge totals `447168734.22717791 / 447164972.07931664 / 445319199.16281865 / 453801638.26270027 / 458736335.45403676` exactly |
| `ROWNUM` batching before `ORDER BY` | `PURGE_ELIGIBLE` | `ROWNUM <= n` is applied before `ORDER BY`, so a batch is an arbitrary n rows, then sorted: first 5 by `ROWNUM` = `DA...033, 039, 045, 051, 057`; first 5 by key = `DA...003, 009, 015, 021, 027` | not ported (purge). Any Snowflake batching uses `ORDER BY ARCH_KEY LIMIT n` (probe: deterministic `A,B` of `B,A,C`) | intent view keys ordered by `ARCH_KEY` equal the Oracle set-based ordered list; a test asserts no Snowflake SQL uses `LIMIT` without `ORDER BY` |
| `RAISE_APPLICATION_ERROR` -20001..-20004 | package spec constants, body | -20001 confirmation missing, -20002 unknown code (incl. lowercase `f07r` and blank), -20003 non-terminating chain, -20004 bad EBCDIC date | Snowflake Scripting `DECLARE e EXCEPTION (-20002, '...'); RAISE e;` keeps the code (probe: `SQLCODE` -20002, `SQLSTATE P0001`). SQL UDFs cannot raise, so set-based views surface -20002/-20003 as rows that VALIDATE rejects; -20001 is replaced by the overlay `purge` flag (dry run by default); -20004 by LOAD `DATE_INVALID` | per code: Oracle input -> error code; Snowflake same input -> same code (procedure) or the documented reject rule (view/LOAD) |
| Blank-padded `CHAR` comparison, `RTRIM(x) IS NULL` | all `CHAR(4)` codes, `V_POLICY_LINEAGE`, `RESOLVE_CLASS` (`RPAD(NVL(p,'    '),4)`) | `POLICY_CODE = 'FIN7 '` matches (1 row); a `VARCHAR2` bind `'FIN7 '` does not (0 rows); `RTRIM('    ') IS NULL` is true (37 terminal codes) | Snowflake `CHAR` is `VARCHAR`: probe `'FIN7 ' = 'FIN7'` false, `RTRIM('    ') = ''` true, `RTRIM('    ') IS NULL` false; case-sensitive like Oracle (`'FIN7' = 'fin7'` false). Compare on `RTRIM(code)`, test terminal as `NULLIF(RTRIM(x), '') IS NULL`; keep padded keys only for the business hash (`CONTRACTS.md` §7) | 37 terminal codes and 3 successor codes identical; join `DOCARCH.RETENTION_CLASS` to lineage finds 1,200,000 rows in both; lowercase code resolves to nothing in both |
| `NUMBER(31,8)` and `ROUND(...,8)` | `DOCARCH.STORAGE_CHARGE/UNIT_RATE`, `CLASS_TOTAL_SNAP.CHARGE_TOTAL`, `CLASS_TOTALS` | exact decimal; 5 `UNIT_RATE` values are `12345678901234.56789001..05` | `NUMBER(31,8)` native; `SUM` returns `NUMBER(38,8)` (probe), so `ROUND(...,8)` is a no-op but kept. `ARCH.DOCARCH.UNIT_RATE` is `NUMBER(18,8)` per the manifest override: probe cast raises 100046 "Number out of representable range", i.e. those 5 rows are LOAD `DECIMAL_OVERFLOW` rejects, not silent truncation | class totals above exact to 8 dp (compare as text, never float: a float fetch reads `447168734.2271779`); the 5 overflow keys are rejected with SQLSTATE 22003 |
| `TIMESTAMP(9)` | `LAST_ACCESS_TS`, `EVENT_TS`, `EFFECTIVE_TS`, `SNAP_TS` | 9 fractional digits kept: 1,198,771 `DOCARCH` and 4,095,887 `FILEAUD` rows have non-zero sub-microsecond digits | `TIMESTAMP_NTZ(9)` keeps all 9 (probe `...30.123456789`); `ARCH.*` stores `TIMESTAMP_NTZ(6)` + `_NANOS_TAIL` (probe: `NTZ(6)` truncates to `...30.123456000`). PostgreSQL `mig.*` is microsecond-only, so full precision lives in the tail, never in the control plane | reconstruct `TO_CHAR(ts,'...FF6') || LPAD(tail, 3)` for every row and compare to Oracle `TO_CHAR(ts,'...FF9')`; eligibility at the cutoff boundary identical (180,000) |
| `RAW` + `UTL_RAW.CONVERT` EBCDIC 037 | `DOCARCH.OWNER_NAME RAW(40)`, `DISPOSITION_DT RAW(8)`; `DISPOSITION_DT_TEXT`, `V_LEGAL_HOLDS` | `F2F0F2F3F0F2F2F8` -> `20230228`; 5 low-values rows -> NULL; `C1C2...` -> -20004; 5 `OWNER_NAME` values contain `X'3F'`, shown as-is in `V_LEGAL_HOLDS` | no EBCDIC conversion in Snowflake SQL (inference; `HEX_DECODE_STRING`/`TO_BINARY` do not change code page). Decode stays in the engine's LOAD (`encoding: cp037`): `X'3F'` -> `CCSID_UNMAPPABLE`, low-values -> `DATE_INVALID`. A SQL-only digit check is possible (probe: `REGEXP_LIKE(HEX_ENCODE(b), '(F[0-9]){8}')`, `REGEXP_REPLACE(..., 'F([0-9])', '\\1')` -> `20230228`) | 1,199,995 `DISPOSITION_DT` values decode to the same `YYYYMMDD` in both; 5 low-values and 5 `X'3F'` keys appear as LOAD rejects with those rule names; `V_LEGAL_HOLDS.OWNER_NAME` identical for held rows |
| `ORA-01839` leap-day fallback, `ADD_MONTHS` month-end | `DISPOSITION_DATE`, `NEXT_REVIEW_DATE`, `CUTOFF_TS` | 2012-02-29 + 7 y -> 2019-02-28; `NEXT_REVIEW_DATE(2010-08-31, BRD9)` -> 2020-02-29 (ADD_MONTHS keeps month-end); 917 documents last accessed on 29 Feb | `DATEADD(year, 7, '2012-02-29')` -> 2019-02-28 and `ADD_MONTHS('2019-08-31', 6)` -> 2020-02-29 match. Trap: `DATE_FROM_PARTS(2019, 2, 29)` returns 2019-03-01 (rolls over, no error), so a literal port of the "build YYYYMMDD then catch" logic silently moves the date | all 917 leap-day documents and a month-end fixture: `DISPOSITION_DATE` / `NEXT_REVIEW_DATE` identical; `CUTOFF_TS(2026-01-01)` = 2019-01-01, `CUTOFF_TS(2027-06-15)` = 2020-01-01 |
| Row trigger `FOR EACH ROW WHEN`, `:NEW`/`:OLD` | `TRG_DOCARCH_HOLD_AUDIT` | on hold flip: one `FILEAUD` row `TRG<17 digits>`, `HOLD`/`RLSE`, `SYSTIMESTAMP`, session user, client IP, disposition code; never fired yet (0 `TRG%` rows, sequence at 1) | Snowflake has no triggers. `ARCH.SET_LEGAL_HOLD(arch_key, flag)` procedure does update + audit insert in one transaction, capturing `CURRENT_USER()`; client IP has no reliable equivalent and must be passed by the caller or dropped (decision). A stream on `ARCH.DOCARCH` + task can detect flag changes made outside the procedure | fixture: flip hold Y->N->Y on 3 keys; Oracle (in a rolled-back transaction on a scratch copy, not production) and Snowflake produce the same event types, detail text, disposition codes and 1 event per flip; a no-op update (same flag) writes nothing in both |
| `DBMS_SCHEDULER` calendar job | `NIGHTLY_DISPOSITION` | `PLSQL_BLOCK` daily 02:00, `enabled FALSE`, `max_failures 3`, start date in UTC | task with `USING CRON 0 2 * * * UTC`, created suspended; `SUSPEND_TASK_AFTER_NUM_FAILURES = 3` for `max_failures` | task `SHOW TASKS` state `suspended`, schedule string as above; `EXECUTE TASK` once on scratch writes 5 `CLASS_TOTAL_SNAP` rows equal to `V_CLASS_TOTALS` |
| Package state (`g_closed_schedule`, `c_default_as_of`, `c_max_hops`) | `RETENTION_PKG` spec + init block | schedule membership hard-coded in the init block (comment: "the schedule table never got built"); as-of fixed at 2026-01-01 | reference table `ARCH.RETENTION_SCHEDULE (SCHEDULE_CODE 'CLSD7Y', POLICY_CODE)` loaded with the 5 codes; as-of passed by the caller (run manifest `last_access_before`); hop limit a view constant | table contents equal the init block; eligibility count 180,000 with as-of 2026-01-01 in both |
| `NVL`, `DECODE` | trigger, `V_LEGAL_HOLDS`, body | `DECODE` treats NULL = NULL | native in Snowflake with the same semantics (probe: `DECODE(NULL, NULL, ...)` matches) | covered by the view/trigger tests above |
| PL/SQL functions called per row from SQL | `V_ELIGIBLE_DOCS`, `V_CLASS_TOTALS`, trigger | `V_ELIGIBLE_DOCS` count takes 28.45 s; the equivalent set-based join takes 0.36 s (180,000 rows both) | set-based views; scalar SQL UDFs only for pure date/code arithmetic | row-for-row `EXCEPT` both ways between Oracle `V_ELIGIBLE_DOCS` and Snowflake view (180,000 rows, all code `10`, 5 NULL stored dates) |
| Sequence-generated keys | `SEQ_FILEAUD_TRG` in trigger | `NOCACHE`, gap-free in practice | Snowflake sequence (unique, may gap) | uniqueness + `TRG` prefix + 20-char length; no ordering assertion |
| FK child-first delete, `BULK COLLECT` loop | `PURGE_ELIGIBLE` | deletes `FILEAUD` children then `DOCARCH` parent per key | not ported; Snowflake FKs are not enforced, so it could not provide the guard anyway | see section 5 |

## 5. Behaviours that must NOT be ported

**Destructive purge stays in the PostgreSQL control plane.** `RETENTION_PKG.PURGE_ELIGIBLE`,
`LOG_PURGE`, error -20001, `MIGAUDIT.PURGE_LOG` and the ownership of `MIGAUDIT.PURGE_AUDIT` are not
ported to Snowflake. Deleting from the source is the migration engine's `purge` stage
(`migration/CONTRACTS.md` §4.2 and §9.4.4):

- It is enabled only by the overlay `purge: true` (§4.2); absent or false is a dry run. That flag is
  the replacement for the confirmation phrase.
- It deletes exactly the keys with `mig.validation.purge_safe = 1` for the run; Guard A exits 3 when
  intended != validated.
- Per batch it commits `mig.purge_audit` `INTENDED` in PostgreSQL, then in one Oracle unit of work
  inserts `MIGAUDIT.PURGE_AUDIT` and deletes; Guard B rolls back when the delete count differs from
  the batch or the FK fires. Restarts skip keys already `PURGED`.
- Reference tables are never purged; failed rows stay in the source.

Why `PURGE_ELIGIBLE` becomes an intent/report in Snowflake, not a delete:

1. Snowflake is the copy. Purge removes the source after the copy is proven; a delete in Snowflake
   would remove the archive, not the source.
2. The package decides from live eligibility (lineage, hold flag, cutoff), not from validation. It
   would destroy rows that failed migration (the five `X'3F'` owners and five low-values dates are
   eligible and fail LOAD) and has no count guard. On this database it would delete 619,995 `FILEAUD`
   children by parent, while the engine purges `FILEAUD` keys it selected and validated itself
   (620,000 selected, orphans rejected).
3. Its batches are `ROWNUM` before `ORDER BY` (non-deterministic), its log is autonomous, and its
   parent/child order depends on an enforced FK. Snowflake has none of the three guarantees.
4. Two authorities that can delete means two answers to "why is this row gone"; the audit trail in
   `mig.purge_audit` / `MIGAUDIT.PURGE_AUDIT` is only complete if the engine is the single writer.

What Snowflake gets instead (proposal, not built): `MIG.V_PURGE_INTENT`, read-only, one row per
`(RUN_ID, TABLE_NAME, SOURCE_KEY)`, joining the legacy eligibility (`ARCH.V_ELIGIBLE_DOCS` and its
`FILEAUD` children) to the mirrored verdict `MIG.VALIDATION.PURGE_SAFE`, classified as
`ELIGIBLE_AND_SAFE`, `ELIGIBLE_NOT_SAFE` (legacy would have deleted, engine will not) and
`SAFE_NOT_ELIGIBLE` (engine will delete, legacy rules would not, e.g. a row under legal hold inside the
manifest selection). It is evidence for the purge approval and the reconciliation report, never an
input to a delete. Parity/acceptance tests:

- `COUNT(ELIGIBLE_AND_SAFE)` per table = `mig.run_ledger.purge_intended` for the run.
- DOCARCH eligible keys = Oracle set-based eligible keys (180,000), `EXCEPT` both ways empty.
- `SAFE_NOT_ELIGIBLE` with `LEGAL_HOLD_FLAG = 'Y'` = 0 before any purge is approved (baseline:
  the 180,000-row selection contains no held document).
- Static test: no Snowflake DDL under `migration/target/snowflake/` contains `DELETE FROM ARCH.`.

Also not ported: `MIGAUDIT` as a schema (engine-owned), the partition and index physical design
(Snowflake micro-partitions), and the schema-only `CREATE USER` accounts (Snowflake schemas and
roles come from the tenant bootstrap).

## 6. Ten most expensive rewrites

Ranked by effort, then risk.

| rank | object | effort | risk | why it is expensive | proving parity test |
|---:|---|---:|---|---|---|
| 1 | `ARCHIVE.TRG_DOCARCH_HOLD_AUDIT` | 13 | H | No triggers in Snowflake; needs a single-writer hold procedure, a decision on who may change holds in the archive after cutover, and a substitute for session user / client IP | hold flip fixture: same events, codes and detail text; no-op update writes nothing |
| 2 | `ARCHIVE.V_POLICY_LINEAGE` | 8 | H | Snowflake `CONNECT BY` lacks `NOCYCLE`/`CONNECT_BY_ISLEAF` and hangs on cycles; bounded recursive CTE must reproduce leaf-only, path text and cycle cut; lineage decides class totals | 40-code lineage identical; cycle fixture; FIN7/LGL7 charge sums to 8 dp |
| 3 | `ARCHIVE.V_ELIGIBLE_DOCS` | 8 | H | Five per-row package calls to unwind into one set-based join without changing any row | `EXCEPT` both ways empty over 180,000 rows |
| 4 | `ARCHIVE.RETENTION_PKG` (body) | 8 | H | 13 subprograms, package state, four error codes, leap-day and month-end date arithmetic | per-subprogram fixtures in section 3/4 |
| 5 | `RETENTION_PKG.PURGE_ELIGIBLE` -> `MIG.V_PURGE_INTENT` | 5 | H | Replaces a destructive procedure with a report that must reconcile with the engine's ledger | intent = `purge_intended`; held-and-safe = 0 |
| 6 | `RETENTION_PKG.RESOLVE_CLASS` | 5 | H | Error-raising scalar lookup becomes set-based; CHAR padding and case sensitivity | unknown/blank/lowercase/cycle fixtures map to the same outcome |
| 7 | `ARCHIVE.DOCARCH` (types) | 5 | H | `TIMESTAMP(9)` split, EBCDIC `RAW` decode, `NUMBER(31,8)` vs the `NUMBER(18,8)` override | nanosecond reconstruction for 1,198,771 rows; decode and reject counts |
| 8 | `RETENTION_PKG.DISPOSITION_DATE` / `NEXT_REVIEW_DATE` | 3 | H | Oracle relies on an exception for 29 Feb; Snowflake's `DATE_FROM_PARTS` rolls over silently | 917 leap-day documents + month-end fixture identical |
| 9 | `ARCHIVE.NIGHTLY_DISPOSITION` + `SNAPSHOT_CLASS_TOTALS` | 3 | M | Scheduler semantics (failures, restart, suspended state) and a new snapshot table | task suspended; one execution equals `V_CLASS_TOTALS` |
| 10 | `ARCHIVE.V_LEGAL_HOLDS` | 3 | M | EBCDIC owner name moves to LOAD; correlated subqueries over 4.1 M audit rows | 14,401 held rows, 49,128 events, 6,687 with a hold event |

Section 2 totals 75 points; the 49 points outside native/engine-owned rows are the port, of which the
four H-risk rewrites (ranks 1-4) are 37.
