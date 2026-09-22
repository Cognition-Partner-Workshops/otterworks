# 02_tolerances — correctness contract, version `tol-1` (APPROVED at STOP A, 2026-09-22)

Recon mode: **OFFLINE**. The harness runs only against the local Oracle Free fixture and local MongoDB. A fixture PASS proves the mapping spec and the loader agree on synthetic data; it is never parity with production. The customer must run LIVE or SNAPSHOT recon inside their network before STOP C.

## Per-type rules (from the Oracle profile; strict by default)

| # | Source type / trap | Target | Rule | Recommended value |
|---|---|---|---|---|
| T1 | `NUMBER(p,0)`, p ≤ 18 (`code_val`, `units`, `line_no`, `attempt_no`, `*_cd`, `hist_id`, `log_id`, `eav_id`, `batch_no`) | `long` | exact | exact |
| T2 | `NUMBER(p,s)`, s > 0 (`monthly_fee 12,2`, `overage_rate 12,6`, `*_amt 14,2`, `qty 12,3`, `unit_price 14,4`) | `Decimal128` | `decimal_round` half_even at declared scale; never double | `numeric_abs_tol = 0` |
| T3 | `DATE` (`starts_on`, `issued_on`, `logged_at`, …) | `date` | seconds precision; session TZ assumed UTC; `datetime_utc_truncate_ms` | exact after UTC |
| T4 | `TIMESTAMP` (`occurred_at`, `issued_at`, `sent_at`, `created_at`) | `date` | sub-ms digits truncated | exact at ms |
| T5 | `CHAR(1)` `*_yn`, `flag_NN`, `posted_yn` | `bool` | `rstrip_spaces` then `yn_to_bool` (Y→true, N→false); NULL stays missing | exact |
| T6 | `VARCHAR2` / `CHAR` strings | `string` | `rstrip_spaces` on CHAR only; case preserved (no NLS case-insensitive comparisons found) | exact |
| T7 | Oracle empty string `''` (is NULL in Oracle) | — | `empty_string_is_null`, target policy **missing field** | missing |
| T8 | NULL vs missing field | — | `null_missing_equiv` **on** (a NULL source column and an absent target field compare equal) | equivalent |
| T9 | `VARCHAR2(9)` `*_dt` text dates (`signup_dt`, `invoice_dt`, `due_dt`, `udf_dt_NN`, `eav.created_dt`) | `date` | `date_string_to_date` format `DD-MON-YY` (English), unparseable → missing + quarantine row (source itself returns NULL: `packages/01_pkg_util.sql:55-62`; the extract uses `DD-MON-RR`: `etl/legacy-extra/tools/oracle_custbill_extract.py:19`) | format `%d-%b-%y` |
| T10 | `VARCHAR2(20)` `hist_dt` (`TO_CHAR(SYSDATE,'DD-MON-YY HH24:MI:SS')`, `schema/01_tables.sql:218`) | `date` | `date_string_to_date` format `%d-%b-%y %H:%M:%S` | exact |
| T11 | CSV lists `related_acct_ids`, `child_acct_ids`, `promo_codes_csv`, `gl_acct_csv` | `array<string>` | `csv_to_array` delimiter `,`, trim, drop empty | exact, order preserved |
| T12 | Row counts per collection / embedded array | — | exact | 0 difference |
| T13 | Aggregates (`SUM` of every Decimal128 amount, `COUNT`) | — | `aggregate_rel_tol` | 0 |

## Harness numeric values (`02_tolerances.json`)

| Key | Value | Meaning |
|---|---|---|
| `full_diff_row_threshold` | 100000 | above this, keyed sample + full aggregates instead of full row diff |
| `sample_size` | 1000 | rows per keyed sample |
| `numeric_abs_tol` | 0 | Decimal128 compares exactly after half_even rounding |
| `aggregate_rel_tol` | 0 | sums and counts exact |
| `source_concurrency` | 1 | at most one recon query on the (fixture) source at a time |

## Process rules
- Re-run cap: 3 full recon runs per unit, then escalate (rule 7).
- Amendment: a tolerance changes only by explicit human approval, recorded as a new dated row here (old row kept), a new `version` in both files, and the list of units to re-verify. Grading-only fixes (canonicalization rule or harness bug, no value change) are pre-approved and reported at wave close.
- Recon artefacts under `.migration/recon/` are redacted by the harness default; verdicts are never edited by hand.

## History
| Date | Version | Change | Approved by |
|---|---|---|---|
| 2026-09-22 | tol-1 | initial proposal | pending STOP A |
| 2026-09-22 | tol-1 | approved at STOP A; customer reply, verbatim: "Approved" | customer (this session) |
