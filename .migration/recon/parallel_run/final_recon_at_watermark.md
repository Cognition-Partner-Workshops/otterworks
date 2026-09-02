# Cutover step 1 — Final recon at the watermark (v2, post fix pass)

Supersedes `tp-run/mongodb-20260901T205236Z--parallel-run:.migration/recon/parallel_run/final_recon_at_watermark.md`
(watermark `0150de08`, pre-fix-pass). This is the record of the **last parallel-run cycle (cycle 3)**, which doubles as the
"final recon at the watermark" for the cutover runbook. Full ledger: `evidence_log.md` / `evidence_log.json`; raw artefacts:
`evidence/cycle3/`. Devin does **not** execute a production repoint; this document is evidence for the human STOP C decision
after the independent audit.

## Watermark

| Item | Value |
|---|---|
| Code head (loaded + gated) | `74ecd69e98876b8da26336a6d7cc24eba3e74697` on `tp-run/mongodb-20260901T205236Z` (fix pass merged: PR #1457 @ `7791a93e` → `5fe2af81`; decision rows #19–#20) |
| Source watermark | seed `714559852` · `batch_no 85559852` · `source_ns demo` · manifest sha256 `0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89` · `FIXTURE_META.INITIALIZED_AT 2026-09-01 20:53:10.961888` |
| Spec versions | mapping v1.0.1 (`57de55f2…`) · tolerances v1 (`d67ccdda…`) · canonicalization v1 (`527cf87c…`) — unchanged |
| Target | `ow_tp_mongodb_205236` (quarantine `ow_tp_mongodb_205236_quarantine`), `ns = mongo_205236`, secret `MONGODB_ATLAS_URI` (name only) |
| Full-estate load (from head) | 2026-09-02 06:59:25 → 07:02:29 UTC, 10 loaders, all rc 0 |
| Final cycle (cycle 3) | **2026-09-02 07:11:21 → 07:16:00 UTC** (278.4 s wall; replay clones U6–U9 re-loaded from head first, 36.1 s) |
| Source state | pre == post (plain-SQL/scan read-back identical; 8/8 reads across the session identical; `BILLING_AUDIT_LOG` 1 row, `SEQ_BILLING_AUDIT_LOG` 2 throughout) |

## Cycle 3 — per-unit gate results (harness `result.json` verdicts; 0 findings, 0 warnings)

| Unit | Gate | T1 | T2 | T3 (mode) | T4 | Verdict | Wall |
|---|---|---|---|---|---|---|---|
| U0 reference | `recon run` (oracle, unit projection) | 3 | 14 | 104 (full_diff) | — | PASS | 4.2 s |
| U1 customers | `recon run` | 3 | 313 | 33,333 (full_diff; 25,000 roots + 8,333 graded `attributes`) | — | PASS | 104.3 s |
| U2 invoices | `recon run` | 2 | 9 | 168,713 (full_diff; 18,750 roots + 149,963 graded `lines`) | — | PASS | 21.6 s |
| U3 documents | `recon_ext/recon_pg.py` (postgres) | 3 | 18 | 16,260 (full_diff; 2,000 + 384 roots, 13,876 graded `versions`) | — | PASS | 6.2 s |
| U4 files | `recon_ext/run_dynamo_recon.py` | 1 | 12 | 10,000 (full_diff) | — | PASS | 5.6 s |
| U5 billing core | `recon run` | 11 | 53 | 902 (full_diff) | — | PASS | 13.2 s |
| U6 PKG_OW_UTIL+PKG_PLANS | `scripts/tp_mongo/recon_u6.py` | 14 | 67 | 1,006 | 5 (PLANS-001…005) | PASS | 20.4 s |
| U7 PKG_RATING | `recon_ext/recon_u7.py` | 5 | 23 | 892 | 8 (RATING-001…008) | PASS | 9.7 s |
| U8 PKG_INVOICING | `recon_ext/recon_u8.py` | 8 | 36 | 902 | 6 (INVOICE-001…006) | PASS | 16.8 s |
| U9 PKG_DUNNING | `recon_ext/recon_u9.py` | 7 | 39 | 145 | 5 (DUNNING-001…005) | PASS | 35.0 s |

Tier-4 provenance (U7/U8/U9): `oracle_source_sha 0d326cad54d94cd64e8abb53585b37436eaad2193fdc15ba3596fbb8db3f0d55`,
`transcripts_match: true`. Every `result.json` is identical to cycles 1 and 2 modulo `generated_at`.

## Guards (cycle 3)

- **ns-scoped count guard: PASS 18/18** — for every mapped collection `count({ns:"mongo_205236"}) == count({}) ==` independent
  source root count `==` harness Tier-3 population (codes 32 · tenants 69 · plans 3 · customers 25,000 · customers_history 0 ·
  invoices 18,750 · documents 2,000 · document_snapshots 384 · files 10,000 · subscriptions 69 · subscriptions_history 0 ·
  usage_events 814 · rating_periods 3 · billing_invoices 3 · credit_notes 5 · dunning_attempts 1 · notifications 1 ·
  billing_audit_log 1).
- **Quarantine ceiling (≤ 0.5 %): PASS** — U1 81/25,000 = 0.324 % (`dirty_signup_dt` 50, `bad_csv_list` 31) · U2 37/18,750 =
  0.197 % (`invoice_feed_orphan_lines`) · U3 6/2,384 = 0.252 % (`orphan_document_snapshots`) · U0/U4–U9 0 (none declared).
  Quarantine DB contains exactly the 4 declared classes.
- **Fix-pass acceptance (informational, read-only probe after cycle 3)**: golden `counters` 5/5 `== USER_SEQUENCES.LAST_NUMBER`
  (F-X-1); every `lines[].invoice_id == parent _id` on golden and all replay clones incl. `replay_u8` post-replay 17/17 (F-U8-1).

## Parallel-run verdict

**GREEN — 3 consecutive GREEN cycles (1, 2, 3) at watermark `74ecd69e` / seed 714559852 / batch_no 85559852 / manifest
`0f472286…`; streak 3, red_runs [].** The idle static fixture showed no drift over 8 source reads, so the cutover watermark is the
same source watermark the wave reports and this parallel run reconciled against.

## Carried to STOP C (explicit decision lines, not gate failures)

- F-U8-2 / F-U7-1: Mongo accepts re-finalising/issuing a fixture-seeded period whose id ≠ `md5(tenant||start)`; Oracle raises `ORA-02291`.
- Partial application scope (routes / document & file services still reading legacy) — cutover wiring is orchestrator scope.
- Runbook items: F-U2-2 (U2 loader drop-then-insert, no staging swap), F-U4-1 (`files.size_bytes` int32 vs declared long),
  F-FIX-2 (U6 replay seeder `LAST_NUMBER-1`, clone-only), `MONGODB_ATLAS_URI` not supplied to legacy-billing by any deployment path.

Cost of this session: 1 full-estate load (184 s) + 3 cycles (238.7 s / 268.3 s / 278.4 s) = 30 gates, 8 clone reloads, 6 guard
runs, 8 source reads, 1 acceptance probe; ~17 min wall, all serial (source-load cap 1).
