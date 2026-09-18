# 02_tolerances.md (version tol-1)

Recon mode: OFFLINE (`recon_mode: offline`). DDL scripts plus a read-only DBMS_METADATA dump from the local Oracle container. The harness runs against the local fixture (Oracle in Docker, mongo:7 in Docker). A fixture PASS is never parity. The customer runs LIVE or SNAPSHOT recon inside their network before STOP C is closed.

| Source type | Target type | Rule |
|---|---|---|
| NUMBER(p,s) | Decimal128 | exact, `decimal_round` half_even at scale s |
| NUMBER (integer) | long | exact |
| DATE, TIMESTAMP | date | exact after UTC normalization, truncate to ms |
| VARCHAR2 | string | exact; empty string treated as null (Oracle `'' IS NULL`) |
| CHAR | string | exact after `rstrip_spaces` |
| CHAR(1) *_YN | bool | `yn_to_bool`, Y/N only |
| VARCHAR2 *_CSV, *_IDS | array | `csv_to_array`, delimiter `,`, drop empty |
| VARCHAR2(9) DD-MON-YY date strings (SIGNUP_DT, INVOICE_DT, HIST_DT) | date, or string when unparseable | parse; unparseable kept verbatim in `<field>_raw` and counted |
| RAW(16) uuid | string uuid | exact (lowercase hyphenated) |

- Row-diff threshold: 100,000 (above it, keyed sample of 1,000 plus full aggregates).
- Numeric abs tolerance: 0. Aggregate rel tolerance: 0.
- Source query cap: 1.
- Re-run cap: 3 full recon runs per unit, then escalate.
- NULL vs missing field: `null_missing_equiv`.
- Amendment rule: a tolerance changes only by explicit approval, as a new dated row with a new `version` in both files; merged units named for re-verification. Grading-only fixes are pre-approved and logged.
