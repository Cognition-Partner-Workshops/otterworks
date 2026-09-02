# Parallel run — evidence log (Reconciliation & Parallel Run, Part 2 · Cutover step 1)

Run `tp-run/mongodb-20260901T205236Z` · target `ow_tp_mongodb_205236` (quarantine `ow_tp_mongodb_205236_quarantine`) · `ns = mongo_205236` ·
mapping **v1.0.1** (`03_mapping_spec.json` sha256 `57de55f24c241c51…7bb45`) · tolerances **v1** (`d67ccdda431baa5d…4ada7`) ·
canonicalization **v1** (`527cf87c699275bd…3eb9`) · harness `mongo-migration-plugin-6d021e15/0.2.1` (`recon selftest` PASS, 9 rules) ·
mode **LIVE** on the parent machine's canonical fixtures (Oracle `localhost:52521/FREEPDB1` user `ow_billing`; Postgres
`localhost:5432/otterworks` schema `otterworks_demo`; LocalStack DynamoDB `localhost:4566` table `otterworks-file-metadata`) ·
secrets by NAME only (`MONGODB_ATLAS_URI`, `OW_BILLING_FIXTURE_DSN`, `OW_PG_DSN`, `AWS_ENDPOINT_URL`) · recon params
`--seed 714559852 --param batch_no=85559852 --param source_ns=demo` · source-load cap 1 (every load, gate and probe strictly serial).
Session 2026-09-02 05:25 → 05:44 UTC, separate clone `~/cutover_work/otterworks` on branch
`tp-run/mongodb-20260901T205236Z--parallel-run`; parent checkout untouched; fixtures neither restarted nor reseeded; legacy sources
read with plain SQL / scans only (no PL/SQL invoked). Machine-readable twin: `evidence_log.json` (built from the artefacts under
`evidence/` by `tools/build_evidence.py`; no hand-typed tallies).

## Parallel-run definition (STOP A, decision #3; `02_tolerances.md` "Parallel-run window")

3 consecutive GREEN full-estate recon cycles against the idle fixture (no CDC — the source is a static fixture). A cycle = every
unit's recon gate verbatim (U0/U1/U2/U5 harness `recon run` through the unit projection of `03_mapping_spec.json`; U3/U4 via the
`.migration/recon_ext` Postgres/DynamoDB adapters; U6–U9 Tier-4 transcript-replay drivers, replay clones re-loaded from head
between cycles as the wave-3 report describes) + the ns-scoped count guard + the quarantine-ceiling check (≤ 0.5 % of unit root
rows). A RED cycle is diagnosed (drift vs defect, source re-read twice), never fixed here, and resets the streak.

## Watermark (identity every cycle reconciled AT)

| Item | Value |
|---|---|
| Run-branch head loaded and gated | **`0150de08b072f15969a5a97da655a483b18ed939`** (`tp-run/mongodb-20260901T205236Z`, "cutover workflow phase metadata"; all 10 units merged, rows 11–16 of `05_decisions.md`) |
| Full-estate load window (UTC) | **2026-09-02 05:25:36 → 05:28:40** (184 s, 10 loaders, all rc 0) |
| Source watermark | seed `714559852` · `batch_no 85559852` · `source_ns demo` · manifest `testdata/legacy/manifests/demo.json` sha256 `0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89` (re-verified on the parent checkout) · `FIXTURE_META.INITIALIZED_AT = 2026-09-01 20:53:10.961888` |
| Source population (read **8×** — 2× before the load, pre+post each cycle — all 8 reads identical) | Oracle `CODES` 32 · `TENANTS` 69 · `PLANS` 3 · `CUSTOMER_MASTER` 25,000 (25,000 in batch) · `CUSTOMER_MASTER_HIST` 0 · `ENTITY_ATTR_VALUE` 8,333 · `INVOICE_HEADER` 18,750 (18,750 in batch) · `INVOICE_LINE` 150,000 · `SUBSCRIPTIONS` 69 · `SUBSCRIPTIONS_HIST` 0 · `USAGE_EVENTS` 814 · `RATING_PERIODS` 3 · `RATING_RESULTS` 3 · `INVOICES` 3 · `INVOICE_LINES` 2 · `CREDIT_NOTES` 5 · `DUNNING_ATTEMPTS` 1 · `NOTIFICATIONS` 1 · `BILLING_AUDIT_LOG` 1 (the wave-0 observer row, unchanged) · `SEQ_BILLING_AUDIT_LOG` 2 · `SEQ_SUBSCRIPTIONS_HIST` 1 · `SEQ_CUSTOMER_MASTER` 125,000 · `SEQ_CUSTOMER_MASTER_HIST` 1 · `SEQ_ENTITY_ATTR_VALUE` 11,001 · Postgres `documents` 2,000 · `document_versions` 13,876 · `document_snapshots` 390 · DynamoDB `ns` histogram `{demo: 10000}` |
| Spec inputs | mapping `57de55f2…` · tolerances `d67ccdda…` · canonicalization `527cf87c…` — byte-identical to the files every wave report gated |
| Tier-4 provenance (U7/U8/U9 drivers) | `ORACLE_SOURCE_SHA 0d326cad54d94cd64e8abb53585b37436eaad2193fdc15ba3596fbb8db3f0d55`, `transcripts_match: true` in every cycle |

## Full-estate load from head (one pass, serial; reports written outside the repo; `evidence/load/`)

| Unit | Loader (as in the wave reports) | Wall | Result |
|---|---|---|---|
| U0 | `scripts/tp_mongo/load_u0.py` | 3 s | codes 32 · tenants 69 · plans 3 |
| U1 | `scripts/tp_mongo/load_u1.py` | 28 s | customers 25,000 (attributes 8,333) · customers_history 0 · counters 3 · Q `dirty_signup_dt` 50 · Q `bad_csv_list` 31 |
| U2 | `scripts/tp_mongo/load_u2.py` | 62 s | invoices 18,750 · embedded lines 149,963 · Q `invoice_feed_orphan_lines` 37 |
| U3 | `scripts/tp_mongo/load_u3.py` | 13 s | documents 2,000 (versions 13,876) · document_snapshots 384 · Q `orphan_document_snapshots` 6 |
| U4 | `scripts/tp_mongo/load_u4.py` | 32 s | files 10,000 (staging + rename) · orphaned_metadata 40 (`s3_key_convention:/missing/`, migrated) |
| U5 | `scripts/tp_mongo/load_u5.py` | 9 s | subscriptions 69 · subscriptions_history 0 · usage_events 814 · rating_periods 3 · billing_invoices 3 · credit_notes 5 · dunning_attempts 1 · notifications 1 · billing_audit_log 1 |
| U6 | `scripts/tp_mongo/load_replay_u6.py` | 12 s | `replay_u6_*` 13 collections (U0 + U5 clone + counters) |
| U7 | `scripts/tp_mongo/load_u7.py` | 9 s | `replay_u7_*` 12 collections + counters |
| U8 | `scripts/tp_mongo/load_u8.py` | 10 s | `replay_u8_*` 11 collections + counters |
| U9 | `scripts/tp_mongo/load_replay_u9.py` | 6 s | `replay_u9_*` 7 collections + counters |

The load replaced the child/wave residue in the target: nothing from earlier sessions was reused. Golden collections and the four
quarantine classes were produced by exactly the head's loaders against the live fixture.

## Cycle ledger

Gate commands (identical in every cycle; `evidence/cycleN/<unit>/gate/{result.json,report.md,recon.summary.md}`):

```
recon run --unit {U0|U1|U2|U5} --family oracle --mapping <unit projection of .migration/03_mapping_spec.json> \
  --tolerances .migration/02_tolerances.json --canonicalization .migration/canonicalization.json --mode live \
  --source-dsn-secret OW_BILLING_FIXTURE_DSN --target-uri-secret MONGODB_ATLAS_URI --target-db ow_tp_mongodb_205236 \
  --seed 714559852 --param batch_no=85559852 --param source_ns=demo --out <dir>
python .migration/recon_ext/recon_pg.py --unit U3 --family postgres --unit-only --source-dsn-secret OW_PG_DSN  <same flags>
python .migration/recon_ext/run_dynamo_recon.py --unit U4 --source-endpoint-secret AWS_ENDPOINT_URL          <same flags>
python scripts/tp_mongo/recon_u6.py                                   # fixed args inside (writes .migration/recon/U6, copied out, restored)
python .migration/recon_ext/recon_u{7,8,9}.py --unit U{7,8,9} --source-dsn-secret OW_BILLING_FIXTURE_DSN     <same flags>
```

| Cycle | UTC (start → end) | Watermark | Replay clones reset first | Per-unit verdict (T1/T2/T3[/T4] checks, 0 findings, 0 warnings everywhere) | Count guard | Quarantine ceiling | Source pre==post | Cost | **Verdict** |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-09-02 05:30:42 → 05:34:32 | `0150de08` · seed 714559852 · batch 85559852 · manifest `0f472286…` | no (clones fresh from the full load) | U0 PASS 3/14/104 · U1 PASS 3/313/33,333 · U2 PASS 2/9/168,713 · U3 PASS 3/18/16,260 · U4 PASS 1/12/10,000 · U5 PASS 11/53/902 · U6 PASS 14/67/1,006/**5** · U7 PASS 5/23/892/**8** · U8 PASS 8/36/902/**6** · U9 PASS 7/39/145/**5** | PASS 18/18 collections | PASS U1 0.324 % · U2 0.197 % · U3 0.252 % · others 0 (none declared) | yes | gates 224.8 s · guards 4.2 s · source probes 1.1 s · cycle 230.1 s; 10 gates, 0 loads | **GREEN** |
| 2 | 2026-09-02 05:34:53 → 05:39:21 | same | yes — U6 11.8 s · U7 9.2 s · U8 9.1 s · U9 5.7 s | identical tallies, all PASS | PASS 18/18 | PASS (same rates) | yes | gates 227.9 s · resets 35.8 s · guards 4.2 s · cycle 268.1 s; 10 gates, 4 clone reloads | **GREEN** |
| 3 | 2026-09-02 05:39:29 → 05:43:59 | same | yes — U6 12.0 s · U7 9.9 s · U8 9.9 s · U9 5.9 s | identical tallies, all PASS | PASS 18/18 | PASS (same rates) | yes | gates 226.0 s · resets 37.7 s · guards 3.9 s · cycle 268.7 s; 10 gates, 4 clone reloads | **GREEN** |

- **Streak: 3 consecutive GREEN ending at the last cycle → parallel-run verdict GREEN.** No RED cycle; `red_runs = []`; no
  drift-vs-defect triage was required (source re-read anyway before and after every cycle: identical).
- Every unit's `result.json` is **byte-identical across the three cycles modulo `generated_at`** (per-unit sha in
  `evidence_log.json`), and equals the tallies of the wave reports that attested each merged head (wave0 U0 3/14/104; wave1 U1
  3/313/33,333, U2 2/9/168,713, U3 3/18/16,260, U4 1/12/10,000; wave2a U5 11/53/902; wave2b U6 14/67/1006/5, U7 5/23/892/8; wave3
  U8 8/36/902/6, U9 7/39/145/5).
- Tier-3 mode `full_diff` on every collection (largest populations: invoices 18,750 + 149,963 graded embedded lines; customers
  25,000; documents 2,000 + 13,876 graded versions; files 10,000) — nothing sampled, nothing UNGRADED.

### Count guard (ns-scoped; `evidence/cycleN/guards.json`)

For each of the 18 mapped collections: `count_documents({ns:"mongo_205236"})` == `count_documents({})` == independent source root
count (plain SQL / DynamoDB scan through the mapping `root_where`) == harness Tier-3 population. All 18 equal in all 3 cycles:
codes 32 · tenants 69 · plans 3 · customers 25,000 · customers_history 0 · invoices 18,750 · documents 2,000 · document_snapshots
384 · files 10,000 · subscriptions 69 · subscriptions_history 0 · usage_events 814 · rating_periods 3 · billing_invoices 3 ·
credit_notes 5 · dunning_attempts 1 · notifications 1 · billing_audit_log 1. Replay clones are counted by their own gates' Tier 1.

### Quarantine ceiling (≤ 0.5 % of the unit's root rows, all root collections summed; ns-scoped)

| Unit | Classes (ns docs) | Quarantined / root rows | Rate | Ceiling | OK |
|---|---|---|---|---|---|
| U1 | `dirty_signup_dt` 50 · `bad_csv_list` 31 | 81 / 25,000 | 0.324 % | 0.5 % | ✔ |
| U2 | `invoice_feed_orphan_lines` 37 | 37 / 18,750 | 0.197 % | 0.5 % | ✔ |
| U3 | `orphan_document_snapshots` 6 | 6 / 2,384 | 0.252 % | 0.5 % | ✔ |
| U0, U4–U9 | none declared | 0 | 0 | 0.5 % | ✔ (expected 0, observed 0) |

Quarantine DB holds exactly the four declared classes in every cycle (no undeclared class, every doc carries `ns`). Counts equal the
manifest's planted anomalies (50 dirty dates, 31 malformed CSV lists, 37 orphan lines, 6 orphan snapshots).

## Rules honoured

- Legacy sources READ-ONLY: Oracle observed with plain SQL only (`COUNT(*)`, `FIXTURE_META`, `USER_SEQUENCES`); no `PKG_*` call —
  `BILLING_AUDIT_LOG` stayed at 1 row and `SEQ_BILLING_AUDIT_LOG` at 2 across all 8 reads. Postgres and DynamoDB read/scanned only.
- Writes only to `ow_tp_mongodb_205236` / `ow_tp_mongodb_205236_quarantine` (head loaders; Tier-4 replay clones `replay_u*_*`).
- No tolerance, mapping-shape, canonicalization or migrated-code change; the U6 driver's in-repo artefacts were copied out and the
  checked-in `.migration/recon/U6` restored after each run (`git status` clean after every cycle).
- Source-load cap 1: one loader/gate/probe at a time. Fixtures not restarted or reseeded. No secret value in any evidence file
  (grep-verified). No production repoint executed or prepared.

## Open items carried (not blocking the parallel run; unchanged from the wave reports)

F-U8-1 (`sp_issue_invoice` rebuilt `lines[]` omit mapped `invoice_id`; Tier 4 grades return values, so it is gate-invisible),
F-X-1 (`counters` contract split across `util.log_msg` / `rating.log_msg`; golden `counters` has no audit-sequence doc), F-U8-2/F-U7-1
(fixture-seeded period ids), F-U4-1 (`files.size_bytes` int32 vs declared long, value-exact), F-U2-2 (U2 loader drop-then-insert, no
staging swap — runbook item). These are cutover-runbook / fix-list items for the orchestrator; none changes a gate result.

## Evidence tree (this branch)

`.migration/recon/parallel_run/evidence/{watermark/,load/,cycle1/,cycle2/,cycle3/}` — per cycle: `cycle_start.txt`, `cycle_end.txt`,
`steps.jsonl`, `source_pre.json`, `source_post.json`, `guards.json`, `<unit>/gate/{result.json,report.md,recon.summary.md}`
(+ `tier4_provenance.json` / `tier4_replay.json` where the driver emits them), `<unit>.log`, and for cycles 2–3 the
`reset_U{6,7,8,9}.log` / `*.reset_load_report.json`. Tooling: `tools/{source_check.py,guards.py,full_load.sh,cycle.sh,build_evidence.py,subset.py}`.
