Snowflake DDL for the archive store of a split target (`target.provider: snowflake`, binding:
`../../CONTRACTS.md` §6/§8 and `SNOWFLAKE-PORT-SPEC.md` §3). Idempotent, applied in file-name order by
`ldm init` inside the tenant database `OTTERWORKS_LDM_<TOKEN>` and tracked in `MIG.SCHEMA_VERSION`.

Split: the tenant's PostgreSQL database keeps the transactional control plane (`mig.runs`, `run_ledger`,
`key_ranges`, `rejects`, `validation`, `class_totals`, `purge_audit`, `stage_log` - the
`../postgresql` DDL, applied by the same `ldm init`). Snowflake holds `STG.*` (this run's converted rows,
loaded from Parquet via the internal stage `STG.LDM_STAGE` with `COPY INTO`), `ARCH.*` (the served
archive) and `MIG.*` as a mirror of the verdicts written at promotion / run close, so promotion and the
`MIG.V_*` reporting views are set-based inside Snowflake.

Snowflake `CHAR(n)` is `VARCHAR(n)`: fixed-width values keep their padding as loaded and the hash
expression (`ldm/hashing.py::snowflake_hash_expression`) re-pads keys with `RPAD`. Db2 `TIMESTAMP(12)` is
`TIMESTAMP_NTZ(6)` + `<COL>_NANOS_TAIL INTEGER`. Uniqueness of `(NAMESPACE, SOURCE_KEY)` in `STG.*` is not
enforced by Snowflake; the driver removes cross-run duplicates after each `COPY` and reports them as
`DUPLICATE_SOURCE_KEY` rejects (MIG-06), exactly like the PostgreSQL unique index does.

Account-level objects (role `LDM_ADMIN`, warehouse, service user, per-tenant database + job/reader roles)
are created by `scripts/lib/snowflake-bootstrap.sql` / `scripts/deploy-demo.sh`, not here. Teardown drops
the tenant database (`scripts/teardown-tenant.sh`).

## Retention rules (`200`-`220`): `ARCHIVE.RETENTION_PKG` in Snowflake

The Oracle estate's retention package (`../../source/oracle/ddl/070_archive_retention_pkg.sql`, reports in
`080_archive_views.sql`) ported over `ARCH.*`, applied after `000`-`090` and tracked in `MIG.SCHEMA_VERSION` like
every other file. Nothing in `200`-`220` deletes, truncates, drops or updates: `PURGE_ELIGIBLE` becomes a
*purge intent* and destruction stays with the migration engine (`ldm purge`, whose selection predicate is unchanged).
Parity is proven live by `../../job/tests/test_retention_parity.py` (report in `.demo/retention-parity.{md,csv}`);
`../../job/tests/test_retention_ddl.py` is the offline half.

| `RETENTION_PKG` member | Snowflake object | Notes |
|---|---|---|
| `RESOLVE_CLASS(p_code)` | `ARCH.RESOLVE_CLASS(VARCHAR) -> CHAR(4)` | lineage from `ARCH.V_POLICY_RESOLUTION` (recursive CTE) |
| `RETENTION_YEARS(p_code)` | `ARCH.RETENTION_YEARS(VARCHAR) -> NUMBER(5,0)` | of the resolved class |
| `CUTOFF_TS(p_as_of DEFAULT 2026-01-01)` | `ARCH.CUTOFF_TS(DATE DEFAULT '2026-01-01') -> TIMESTAMP_NTZ(9)` | `ADD_MONTHS(TRUNC(as_of,'YYYY'),-84)` |
| `IN_CLOSED_SCHEDULE(p_code)` | `ARCH.IN_CLOSED_SCHEDULE(VARCHAR) -> NUMBER(1,0)` | `ARCH.CLOSED_SCHEDULE()` = FIN7 LGL7 HRS7 TAX7 AUD7 |
| `IS_ELIGIBLE(code, last_access, hold, as_of)` | `ARCH.IS_ELIGIBLE(...) -> NUMBER(1,0)` | hold `Y` returns 0 before the code is resolved |
| `DISPOSITION_DATE(last_access, code)` | `ARCH.DISPOSITION_DATE(...) -> DATE` | `ARCH.ADD_RETENTION_YEARS` |
| `NEXT_REVIEW_DATE(last_access, code)` | `ARCH.NEXT_REVIEW_DATE(...) -> DATE` | `REVW` classes only, Oracle `ADD_MONTHS(+6)` |
| `DISPOSITION_DT_TEXT(p_raw RAW)` | `ARCH.DISPOSITION_DT_TEXT(BINARY) -> VARCHAR(8)` | CP037 digits, LOW-VALUES -> NULL |
| `DISPOSITION_CODE(code, last_access, hold, as_of)` | `ARCH.DISPOSITION_CODE(...) -> CHAR(2)` | kernel `ARCH.DISPOSITION_CODE_OF` shared with the views and `PURGE_INTENT` |
| `CLASS_TOTALS(p_as_of)` (ref cursor) | `ARCH.CLASS_TOTALS(DATE)` table function | per `NAMESPACE` |
| `SNAPSHOT_CLASS_TOTALS` / `CLASS_TOTAL_SNAP` | not ported | the engine's `mig.class_totals` is the reconciliation record |
| `PURGE_ELIGIBLE(confirm, as_of, batch, purged OUT)` | `MIG.PURGE_INTENT(RUN_ID, AS_OF DEFAULT '2026-01-01', NAMESPACE DEFAULT NULL) -> NUMBER` (`220_purge_intent.py`, registered by `220_purge_intent.sql`) + table `MIG.PURGE_INTENT` | records, never deletes |
| scheduler job `RETENTION_NIGHTLY` | not ported | no Snowflake TASK: the engine schedules and executes deletions |
| `V_POLICY_LINEAGE` (`CONNECT BY NOCYCLE`) | `ARCH.V_POLICY_LINEAGE` | recursive CTE with a path array |
| `V_ELIGIBLE_DOCS`, `V_CLASS_TOTALS`, `V_LEGAL_HOLDS` | `ARCH.V_ELIGIBLE_DOCS`, `ARCH.V_CLASS_TOTALS`, `ARCH.V_LEGAL_HOLDS` | same columns, prefixed by `NAMESPACE` |

Semantic differences handled:

- **Lineage.** `CONNECT BY` becomes `WITH RECURSIVE`. `ARCH.V_POLICY_RESOLUTION` follows `SUCCESSOR_CODE` at most
  8 hops (the package's loop limit) and classifies every code `RESOLVED` / `UNKNOWN` (dangling successor) /
  `CYCLE`; the UDFs turn the last two into `-20002` / `-20003`. `ARCH.V_POLICY_LINEAGE` mirrors `NOCYCLE` +
  `CONNECT_BY_ISLEAF` instead (no hop limit, a cycle stops at its last distinct row, a dangling successor ends at the
  row naming it) - the estate has neither case, so that part is checked in scratch, not against Oracle.
- **`CHAR(4)` codes.** Oracle compares blank-padded `CHAR`, and assigning an argument to the package's `CHAR(4)`
  variable blank-pads (and a 5+ character argument keeps its first four characters only when they match - `FIN7X`
  resolves like `FIN7`). The UDFs `RTRIM` both sides and re-pad results with `RPAD(..., 4)`; NULL and `''` are `'    '`,
  which is unknown (`-20002 ... "    "`).
- **Set-based views.** The Oracle views call the package once per row; the Snowflake views join
  `V_POLICY_RESOLUTION` / `V_POLICY_LINEAGE` on `(NAMESPACE, code)` and call the same inline kernels, so they give
  the per-row UDF answers without a per-row lookup. The scalar UDFs read `ARCH.RETNPLCY` across namespaces
  (the package has no namespace argument) and fail with `-20002` if two namespaces disagree on a code.
- **Timestamps.** Oracle `TIMESTAMP(9)` lands as `TIMESTAMP_NTZ(6)` + `_NANOS_TAIL`; `ARCH.TS9` rebuilds the
  nanoseconds so comparisons against `CUTOFF_TS` and the reported `LAST_ACCESS_TS` match to the nanosecond.
  One exception, measured on the stand-in: `IS_ELIGIBLE` compares in PL/SQL against the `TIMESTAMP` (precision 6)
  cutoff, which rounds the access time half-up to microseconds (`2018-12-31 23:59:59.9999995` is *not* before
  `2019-01-01`), so `ARCH.IS_ELIGIBLE` and `V_ELIGIBLE_DOCS` apply `ARCH.PLSQL_TS6` first. The SQL comparisons
  (`V_CLASS_TOTALS`, `CLASS_TOTALS`, `PURGE_ELIGIBLE`'s cursor) keep all nine digits, and so do `DISPOSITION_DATE` /
  `DISPOSITION_CODE`. No estate row falls in that half-microsecond window; the parity harness covers it synthetically.
- **Leap day.** Oracle `ADD_MONTHS` maps the last day of a month to the last day of the target month;
  `DISPOSITION_DATE` adds whole years with 29 Feb -> 28 Feb in a non-leap year (`ARCH.ADD_RETENTION_YEARS`), and
  `NEXT_REVIEW_DATE` uses Snowflake `ADD_MONTHS`, which snaps month ends the same way (2021-02-28 -> 2021-08-31;
  `DATEADD(month)` would not).
- **Raw -> target decoding.** `DISPOSITION_DT` is `RAW(8)` of CP037 digits in Oracle and a promoted `DATE` in
  `ARCH.DOCARCH`; `DISPOSITION_DT_TEXT` still takes the raw bytes (`BINARY`): all-`0x00` (LOW-VALUES) or NULL ->
  NULL, `F0`-`F9` -> `0`-`9`, anything else `-20004`, more than 8 bytes Oracle's `-6502`. It does not validate the
  calendar (`20190229` stays text), exactly like the package. `ARCH.V_ELIGIBLE_DOCS.DISPOSITION_DT_STORED` renders
  the promoted `DATE` as `YYYYMMDD`. `V_LEGAL_HOLDS.OWNER_NAME` is the CP037-decoded, right-trimmed owner the engine
  promoted (Oracle's `UTL_RAW.CONVERT` from WE8EBCDIC37).
- **Errors.** Snowflake SQL UDFs cannot raise, so `ARCH.RAISE_APPLICATION_ERROR(code, message)` (JavaScript) throws
  and the statement fails with `"<code>: <message>"` in the error text - the package's code and message verbatim.
  `PURGE_INTENT` raises the same way from Python: `-20001` for a missing run id (the confirmation phrase has no
  counterpart - nothing is destroyed) or a run id reused with another as-of; `-20002`/`-20003` if a non-held row's
  class does not resolve (Oracle's FK prevents that; Snowflake does not enforce FKs). `-20004` cannot arise there
  because the selection never reads `DISPOSITION_DT`.
- **Money.** `STORAGE_CHARGE` is `NUMBER(31,8)` on both sides and `CHARGE_TOTAL` is `ROUND(SUM(...), 8)`; Snowflake
  sums `NUMBER(31,8)` into `NUMBER(38,8)`, so the totals are exact and equal to Oracle's digit for digit.
- **Purge intent, not purge.** `MIG.PURGE_INTENT` gets one row per `FILEAUD` child of each eligible parent and then
  the parent (`INTENT_SEQ` per namespace, parents in `ARCH_KEY` order), with `SOR_CLASS`, `SCHEDULE_CODE = CLSD7Y`,
  the parent's `DISPOSITION_CODE` as `REASON_CODE`, `AS_OF_DT` and `CUTOFF_TS`. The selection is
  `PURGE_ELIGIBLE`'s cursor without the `ROWNUM` batch; the return value is the parent count (`p_purged`). A rerun of
  the same `(RUN_ID, AS_OF)` returns the recorded count and writes nothing.
