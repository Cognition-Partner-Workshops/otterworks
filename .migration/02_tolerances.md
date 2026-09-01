# 02 — Tolerance Record (parity contract)

Version: **v1 (FACT — approved at STOP A, 2026-09-01, decision #3)**. Every row is FACT or PROPOSED. Amendments
only by explicit approval as a new dated version with re-verification scope, except
grading-only amendments (no document shape, no tolerance value, no data changed), which
are pre-authorized: apply, log in 05, report at wave close.

## Recon mode and load

| Item | Value | Status |
|---|---|---|
| Recon mode | LIVE — harness holds dual connections (source fixture + Atlas) | PROPOSED |
| Source-load cap | 1 concurrent recon/extract query per source system (`--source-concurrency 1`) | PROPOSED |
| Recon authority | `mongo-recon-harness` `result.json` verdict only; no accelerator, MCP, or manual check self-certifies | FACT |
| Full re-run cap | 3 full end-to-end re-runs per unit; then escalate with evidence | PROPOSED |
| Circuit breaker | 3 same-class failures across units halts that class; escalate to `#ow-tp-alerts` | FACT (plugin guardrail) |
| Parallel-run window | 3 consecutive green recon cycles against the idle fixture before STOP C (no CDC; source is a static fixture) | PROPOSED |

## Per-type canonicalization (Oracle profile `recon_canonicalization`, passed verbatim)

| Source type | Target BSON | Rule | Status |
|---|---|---|---|
| `NUMBER(p,0)`, p ≤ 9 | int32 | exact | PROPOSED |
| `NUMBER(p,0)`, 10 ≤ p ≤ 18 | int64 | exact | PROPOSED |
| `NUMBER(p,s)`, s > 0, or unbounded `NUMBER` | Decimal128 | `decimal_round` half_even at source scale; never double | PROPOSED |
| `DATE`, `TIMESTAMP`, `TIMESTAMP WITH TZ` | date | `datetime_utc_truncate_ms`; fixture session TZ = UTC; `DATE` with no time is midnight UTC | PROPOSED |
| `VARCHAR2`, `NVARCHAR2` | string | byte-transparent; `empty_string_is_null` → target policy **explicit BSON `null`** | PROPOSED |
| `CHAR(n)` | string | `rstrip_spaces` before compare | PROPOSED |
| `CLOB`/`NCLOB` | string | full value; document must stay < 16 MB (checked Tier 3) | PROPOSED |
| `BLOB`/`RAW` | binData | byte-exact | PROPOSED |
| Postgres `timestamptz` / `jsonb` / `uuid` | date / object / string | UTC ms; jsonb key order ignored; uuid lowercase string | PROPOSED |
| DynamoDB `N` / `S` (ISO-8601) / `BOOL` | int64 or Decimal128 / date / bool | `N` integer → int64, else Decimal128; ISO strings ending `Z` → date | PROPOSED |
| NULL vs missing | — | `null_missing_equiv`: source NULL → explicit `null`; harness treats null ≡ missing | PROPOSED |
| Collation | — | `collation_casefold` **disabled** unless census finds NLS case-insensitive comparisons (then re-decided at STOP B as grading-only) | PROPOSED |

## Counts, aggregates, diffs

| Surface | Tolerance | Status |
|---|---|---|
| Root doc count vs root row count (through mapping) | 0 difference | PROPOSED |
| Embedded array cardinality vs child rows | 0 difference, orphans excluded per mapping `orphan_policy` and counted in quarantine | PROPOSED |
| Per-field aggregates (null rate, min/max, sum, distinct) | exact after canonicalization; `SUM`/`COUNT(DISTINCT)` exclude null/missing on both sides | PROPOSED |
| Keyed diff threshold | full keyed diff ≤ 100,000 roots; above: deterministic stratified sample (seed recorded in `result.json`) + full aggregates | PROPOSED |
| Quarantine rate ceiling | ≤ 0.5 % of a unit's root rows; every quarantined doc has a reason class; planted anomalies (dirty dates, malformed CSV lists, orphan lines/snapshots/metadata, version gaps) are expected quarantine/normalization classes and are enumerated in 03 | PROPOSED |
| Tier 4 app parity | recorded representative operations (PL/SQL package entry points via `procs/harness/oracle_record.py` transcripts; document/file API reads) replayed on both stacks; 0 semantic differences after canonicalization | PROPOSED |

## Evidence-integrity rules (FACT)

- Every gate declares its population (source table + `root_where`, target collection +
  filter) in `result.json`; a rate without a population is not evidence.
- No child reconciles against data it generated itself; the fixture manifest checksum
  (`testdata/legacy/manifests/demo.json`) pins the source population for every run.
- Embeds without element key + graded fields are UNGRADED and block a PASS.
- Seed, watermark, `ns`, mapping version, tolerance version recorded in every `result.json`.
- Nothing in this record is relaxed mid-run; ambiguity is escalated, not interpreted.
