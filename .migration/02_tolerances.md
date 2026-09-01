# 02 — Parity contract (tolerances)

**Version:** `v1` (2026-09-01) · **Recon mode:** LIVE · **Status:** PROPOSED pending STOP A

A tolerance changes only by explicit user approval, recorded as a new dated version
(`v2`, …) in `05_decisions.md`, together with the re-verification scope for already-merged
waves.

## Per-type rules

| # | Surface / type | Rule | Status |
|---|---|---|---|
| T1 | Row/doc counts | ZERO tolerance. Root docs == root rows; embedded array cardinality == child rows, minus explicitly quarantined records that are enumerated and counted | PROPOSED |
| T2 | `NUMBER(p,0)`, p ≤ 18 | → BSON `long` (int32 only where p ≤ 9 and the app contract is 32-bit) | PROPOSED |
| T3 | `NUMBER(p,s)` s > 0, or p > 18, or unbounded `NUMBER` | → `Decimal128`, never `double`; comparison rounds half-even at the source scale | PROPOSED |
| T4 | `DATE` / `TIMESTAMP` | → BSON `date`, normalized to UTC (source has no TZ; session TZ treated as UTC), truncated to ms | PROPOSED |
| T5 | `CHAR` (blank-padded) | trailing spaces stripped on load; recon applies `rstrip_spaces` | PROPOSED |
| T6 | Oracle empty string == NULL | Target policy: **field omitted** (no `null`, no `""`). Recon rule `empty_string_is_null` with `target_policy=missing` | PROPOSED |
| T7 | NULL vs missing field | Equivalent for comparison: a source NULL matches an absent target field. Explicit `null` is never written | PROPOSED |
| T8 | String collation | Byte-exact after T5/T6; no case folding (no NLS case-insensitive comparison found in the census probe) | PROPOSED |
| T9 | `VARCHAR2` `DD-MON-YY` string dates (e.g. `SIGNUP_DT`) | Parsed to BSON `date` when valid; unparseable values (50 planted, e.g. `31-FEB-24`, `N/A`) go to quarantine with the original string preserved — never coerced, never dropped silently | PROPOSED |
| T10 | CSV list columns (`RELATED_ACCT_IDS`, `PROMO_CODES_CSV`) | Split to real arrays on `,`, elements trimmed; empty → field omitted; malformed lists (31 planted) quarantined with the raw string preserved | PROPOSED |
| T11 | EAV rows (`ENTITY_ATTR_VALUE`) | Folded into an `attributes` subdocument on the owning root doc; values stay strings (source `attr_type` is always `STR`) unless the mapping spec declares a typed coercion per attribute | PROPOSED |
| T12 | Orphaned child rows (37 `INVOICE_LINE`, and any other FK-violating child) | Quarantined, enumerated, and counted; never embedded, never dropped silently | PROPOSED |
| T13 | Byte transparency | UTF-8 end to end; non-ASCII bytes preserved exactly; no transliteration | PROPOSED |
| T14 | Empty input | An empty source table (`BILLING_AUDIT_LOG`, `*_HIST`) is a valid PASS: the collection is created empty, and the unit records "0 rows, 0 docs, PASS" — it is never skipped silently | PROPOSED |

## Size tiers

| Tier | Row count | Tier-3 diff strategy | Status |
|---|---|---|---|
| Small | ≤ 25,000 | full keyed diff of every row | PROPOSED |
| Large | > 25,000 | full Tier-2 aggregates + keyed stratified sample (seeded, min 5,000 rows or 5%, whichever is greater) | PROPOSED |

Only `INVOICE_LINE` (150,000) is Large at `SCALE=demo`; it is graded as embedded elements of `invoices`.

## Load / evidence integrity rules

- **Source-load cap: 1 concurrent extract/recon query** against Oracle (`--source-concurrency 1`). This, not session width, is the fan-out constraint. PROPOSED.
- **Per-check population is declared per gate**: every rate or count states the exact set of rows/docs it is measured over. A quarantine rate is quarantined ÷ source rows read.
- **Never reconcile against data the child generated.** The comparison baseline is the live Oracle estate (LIVE mode) plus the immutable seed manifest `testdata/legacy/manifests/demo.json`.
- **Re-run cap: 3.** After 3 full recon re-runs on one unit, the child escalates instead of retrying.
- **Circuit breaker:** 3 same-class failures across units halts the wave and escalates.
- **UNGRADED embeds are work, not a pass:** any embedded array without a declared element key/fields is fixed in the mapping spec via the STOP B change process.
- **No child writes shared roots.** Each unit owns disjoint collections registered in `04_progress.md` before loading.

## Anomaly ledger (must be found, not tolerated)

The seed manifest enumerates the estate's known defects. Recon must surface exactly these
counts on the Oracle side — no more, no fewer: 37 orphaned `INVOICE_LINE` rows, 50 dirty
`SIGNUP_DT` strings, 31 malformed CSV lists. Any anomaly no unit ingests is declared a
coverage gap in the mapping spec, not discovered at rollup.
