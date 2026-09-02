# Final recon at the watermark (Cutover step 1) — summary of parallel-run cycle 3

Run `tp-run/mongodb-20260901T205236Z` · target `ow_tp_mongodb_205236` (quarantine `ow_tp_mongodb_205236_quarantine`) · `ns mongo_205236` ·
mapping v1.0.1 · tolerances v1 · canonicalization v1 · LIVE mode on the canonical fixtures · secrets by name only.
Full ledger: `evidence_log.md` / `evidence_log.json`; artefacts: `evidence/cycle3/`.

## Watermark

| Item | Value |
|---|---|
| Code | run-branch head **`0150de08b072f15969a5a97da655a483b18ed939`** (all 10 units merged) — loaded 2026-09-02 05:25:36–05:28:40 UTC, gated 3× |
| Source | seed `714559852` · `batch_no 85559852` · `source_ns demo` · manifest sha256 `0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89` · `FIXTURE_META.INITIALIZED_AT 2026-09-01 20:53:10.961888` · static fixture, no CDC; population identical on all 8 reads across the session (last read 2026-09-02 05:43:59 UTC) |
| Final recon cycle | cycle 3, **2026-09-02 05:39:29 → 05:43:59 UTC** (268.7 s wall, serial under source-load cap 1) |

## Result: **GREEN** (3rd consecutive GREEN cycle; streak 3/3; no RED cycle in the run)

| Unit | Gate | Tier 1 | Tier 2 | Tier 3 (full diff) | Tier 4 | Warnings / findings | Verdict |
|---|---|---|---|---|---|---|---|
| U0 `codes`, `tenants`, `plans` | `recon run` | 3 | 14 | 104 (32/69/3) | — | 0 / 0 | PASS |
| U1 `customers`, `customers_history`, `counters` | `recon run` | 3 | 313 | 33,333 (25,000 roots + 8,333 graded `attributes`) | — | 0 / 0 | PASS |
| U2 `invoices` (+`lines[]`) | `recon run` | 2 | 9 | 168,713 (18,750 roots + 149,963 graded lines) | — | 0 / 0 | PASS |
| U3 `documents` (+`versions[]`), `document_snapshots` | `recon_pg.py` | 3 | 18 | 16,260 (2,000 + 13,876 graded versions + 384) | — | 0 / 0 | PASS |
| U4 `files` | `run_dynamo_recon.py` | 1 | 12 | 10,000 | — | 0 / 0 | PASS |
| U5 billing core (9 collections) | `recon run` | 11 | 53 | 902 (embeds `results` 3 + `lines` 2) | — | 0 / 0 | PASS |
| U6 `PKG_OW_UTIL`/`PKG_PLANS` port, `replay_u6_*` | `recon_u6.py` | 14 | 67 | 1,006 | 5 (PLANS-001…005) | 0 / 0 | PASS |
| U7 `PKG_RATING` port, `replay_u7_*` | `recon_u7.py` | 5 | 23 | 892 | 8 (RATING-001…008) | 0 / 0 | PASS |
| U8 `PKG_INVOICING` port, `replay_u8_*` | `recon_u8.py` | 8 | 36 | 902 | 6 (INVOICE-001…006) | 0 / 0 | PASS |
| U9 `PKG_DUNNING` port, `replay_u9_*` | `recon_u9.py` | 7 | 39 | 145 | 5 (DUNNING-001…005) | 0 / 0 | PASS |
| Count guard (ns-scoped) | `guards.py` | 18/18 collections: ns docs == total docs == independent source root count == harness population | | | | | PASS |
| Quarantine ceiling (≤ 0.5 %) | `guards.py` | U1 81/25,000 = 0.324 % · U2 37/18,750 = 0.197 % · U3 6/2,384 = 0.252 % · others 0; quarantine DB = exactly the 4 declared classes | | | | | PASS |
| Source stability | `source_check.py` | pre == post (Oracle 19 tables + `FIXTURE_META` + 5 sequences, Postgres 3 tables, DynamoDB ns histogram) | | | | | PASS |

Tier-4 provenance for U7/U8/U9: transcripts' `ORACLE_SOURCE_SHA 0d326cad…0d55` matches (`transcripts_match: true`). Replay clones
were re-loaded from the head before this cycle (U6 12.0 s, U7 9.9 s, U8 9.9 s, U9 5.9 s) so Tier 4 ran from the fixture baseline.
Every `result.json` of cycle 3 is byte-identical (modulo `generated_at`) to cycles 1 and 2 and to the tallies of the wave reports
that attested each merged head.

## Cost of the final cycle

Gates 226.0 s (U1 92.1 · U9 37.1 · U2 21.7 · U6 20.2 · U8 17.5 · U5 12.0 · U7 9.7 · U3 5.7 · U4 5.6 · U0 4.4) · clone resets 37.7 s ·
guards 3.9 s · source probes 1.1 s. One source connection at a time; Oracle read with plain SQL only (`BILLING_AUDIT_LOG` still 1 row,
`SEQ_BILLING_AUDIT_LOG` still 2). Nothing restarted, reseeded or modified on the legacy side; writes confined to the target and its
quarantine DB.

## What this attests / does not attest

- Attests: at watermark `0150de08` / seed 714559852 / batch 85559852 / manifest `0f472286…`, the Atlas target `ow_tp_mongodb_205236`
  reconciles exactly (0 findings, full keyed diff, exact aggregates, 0 semantic Tier-4 differences under canonicalization v1) with the
  idle legacy estate across all 10 units, three times in a row, with count guard and quarantine ceiling green.
- Does not attest: any production repoint (Devin never executes one); resolution of the carried non-gate findings F-U8-1, F-X-1,
  F-U8-2/F-U7-1, F-U4-1, F-U2-2 — these remain orchestrator fix-list / runbook items and are unchanged by this session.
- Next: evidence pack + runbook PR → independent audit → STOP C (per `05_decisions.md` row 17).
