# 07 — Evidence pack (STOP C)

Assembled at the cutover watermark, from artifacts each wave produced at its own close.
Nothing here is retyped: every number is read out of the `result.json` it cites, and the
watermark column is a fresh live re-grade rather than a copy of the wave verdict.

- Mapping version: `m1` (ACCEPTED at STOP B) · Tolerances `v1` (ACCEPTED at STOP A)
- Recon mode: `live` (harness reads Oracle and Atlas directly; nothing snapshot-based)
- Source: `OW_BILLING` in `FREEPDB1`, SELECT-only throughout (deviation R1, approved)
- Target: `ow_tp_mongodb_orc1`; `ow_tp_mongodb_demo` and `ow_tp_demo1` untouched
- **Watermark: 2026-09-01T05:13:14Z**

## 1. Final delta catch-up and recon at the watermark

The estate takes no live writes during this run, so the watermark is a timestamp rather
than a freeze: at 05:13:14Z every loaded unit was re-graded live against Oracle with
`.migration/tools/watermark_recon.sh`. A row that had changed since its wave load would
fail tier 1 or tier 3 here — the re-grade is the catch-up check, not a formality.

| Unit | Wave verdict | Watermark verdict | Checks at watermark | Artifact |
|---|---|---|---|---|
| `reference` | PASS | **PASS** | 121 | `recon/reference/watermark/result.json` |
| `customers` | PASS | **PASS** | 33,376 | `recon/customers/watermark/result.json` |
| `subscriptions` | PASS | **PASS** | 78 | `recon/subscriptions/watermark/result.json` |
| `invoices` | PASS | **PASS** | 168,724 | `recon/invoices/watermark/result.json` |
| `usage_rating` | PASS | **PASS** | 832 | `recon/usage_rating/watermark/result.json` |
| `subscription_invoices` | PASS | **PASS** | 15 | `recon/subscription_invoices/watermark/result.json` |
| `collections_ops` | PASS | **PASS** | 30 | `recon/collections_ops/watermark/result.json` |

203,176 checks across tiers 1–3 (counts through mapping, per-field aggregates, keyed
diffs), 0 findings, 0 deltas against the wave loads. Nothing was re-loaded to make this
green: the loads at the watermark are the wave loads.

## 2. Coverage

`census/coverage.md` buckets every source object into fields / folded / dropped, and the
mapping generator fails rather than emitting a spec with an unbucketed column.

| | Source | Disposition |
|---|---|---|
| Tables | 20 | 19 mapped into 13 collections + 2 quarantine collections; `FIXTURE_META` out of scope (estate bookkeeping, one row) |
| Columns | 432 | all bucketed; 113 `CUSTOMER_MASTER` columns dropped as NULL in all 25,000 rows (STOP B decision 3) |
| PL/SQL | 5 packages / 19 routines | converted, `.migration/stored_logic/billing_logic.py` |
| Triggers | 7 | replaced in store logic or by index/TTL, `stored_logic/dispositions.json` |
| Jobs | 2 | one becomes an application scheduler call, one a TTL index |
| Sequences | 5 | retired; natural `_id` throughout (STOP B decision 4) |

## 3. Data delivered

44,646 root documents, 158,301 embedded elements, 118 quarantined records. Quarantine is
evidence, not loss: every quarantined row is stored with its source key, its raw value and
the rule that rejected it, in a `<unit>_quarantine` collection that is never mixed into the
live one.

| Anomaly | Expected at STOP A | Found | Where |
|---|---|---|---|
| Orphaned `INVOICE_LINE` rows | 37 | 37 | `invoices_quarantine` |
| Unparseable `SIGNUP_DT` strings | 50 | 50 | `customers_quarantine` |
| Malformed `RELATED_ACCT_IDS` CSV | 31 | 31 | `customers_quarantine` |

Idempotency is graded, not asserted: each unit was loaded twice and the two machine-readable
load reports are compared on content digest, mapping version, target database and
parameters (`recon_report.py`), so a rerun that converged for the wrong reason still fails.

## 4. Stored-logic (Tier 4) parity

`recon/stored_logic/result.json`, verdict **PASS**:

- 24/24 recorded scenarios match the immutable Oracle transcripts byte-for-byte across
  12 entrypoints, on a fail-closed publication (a partial, stale or edited transcript set
  is refused rather than graded).
- Object inventory 38/38: 19/19 routines, 7/7 triggers, 2/2 jobs, 5/5 sequences
  dispositioned.
- Behaviour is preserved, not improved: the 101-unit tier break, the doubled `LEAST` cap,
  the credit burn-down that decrements an undiminished balance, and Oracle's NULL-propagating
  `LEAST`/`GREATEST` are all reproduced because the transcripts are the acceptance criteria.

## 5. Open issues and dispositions

| # | Issue | Disposition |
|---|---|---|
| 1 | No read-only Oracle principal exists (R1) | Accepted at STOP A; SELECT-only discipline, no source DDL/DML issued this run |
| 2 | Atlas M0 headroom (R2) | Staged wave-by-wave; 220.23 MB free at the last boundary |
| 3 | `CUSTOMER_MASTER_HIST`, `SUBSCRIPTIONS_HIST`, `BILLING_AUDIT_LOG` empty at source | Collections materialized and graded at 0 rather than omitted |
| 4 | Autonomous-transaction audit logging | Independence preserved (log write carries no session); `WHEN OTHERS THEN NULL` deliberately not reproduced; no recorded scenario observes a failing audit write |
| 5 | 4 utility routines no scenario calls directly | Converted and unit-tested, but not transcript-graded — listed as an unverified path |
| 6 | The nightly scheduler itself | The job body is converted and graded; the scheduler that fires it is application infrastructure, out of this run's scope |
| 7 | No live-write parity window | The estate was not written to during the run, so the parallel-run evidence proves stability against a quiescent source only. Re-confirmed as its own STOP C decision line, not inherited |
| 8 | Application repoint | Out of scope at STOP B decision 5; the runbook (`08_cutover_runbook.md` §1) states exactly which paths the repoint covers and which still read Oracle |

## 6. Independent audit

Per `!mongo_cutover` step 3 the audit is run by a session that migrated nothing, from this
pack alone. Its countersignature or findings are recorded in `05_decisions.md` before
STOP C is answered.
