# 08 — Evidence pack index (Cutover & Sign-off, step 2)

Run `tp-run/mongodb-20260901T205236Z` · target `ow_tp_mongodb_205236` (quarantine `ow_tp_mongodb_205236_quarantine`) ·
ns `mongo_205236` · secrets by NAME only (`MONGODB_ATLAS_URI`, `OW_BILLING_FIXTURE_DSN`).

This file is an **index**. It verifies that the evidence exists, is internally consistent and is tied to one watermark;
it re-runs nothing. Every path below is `branch:path` where the artefact lives off the run branch.

## Status: **COMPLETE** (v2, post fix pass) — gap ledger in §8

The parity evidence is complete and green at the watermark (all 10 units, 3 consecutive GREEN full-estate cycles at
run-branch head `74ecd69e`, which contains the F-U8-1/F-X-1 fix pass). Of the five gaps recorded by the v1 pack (watermark
`0150de08`, decision row 18): gaps 1, 2 and 4 are **closed with committed evidence** (§8); gaps 3 and 5 are **converted to
explicit STOP C decision lines** (runbook §H.2, §H.3) by human decision (row 19). Nothing is papered over: every carried
item is still listed in §6 with its disposition.

v1 of this pack (INCOMPLETE, watermark `0150de08`, parallel-run branch `--parallel-run` @ `3279c93b`) is superseded by this
revision and is not relied upon.

## 1. Watermark (single source of truth for the runbook)

| Item | Value |
|---|---|
| Code | run-branch head `74ecd69e98876b8da26336a6d7cc24eba3e74697` (all 10 units merged; post fix-pass merge `5fe2af81` of PR #1457 @ `7791a93e`, decision rows 19–20) |
| Full-estate load | 2026-09-02 06:59:25 → 07:02:29 UTC (10 loaders, all rc 0) |
| Source identity | seed `714559852` · `batch_no 85559852` · `source_ns demo` · manifest sha256 `0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89` · `FIXTURE_META.INITIALIZED_AT 2026-09-01 20:53:10.961888` |
| Versions | mapping **v1.0.1** (`57de55f2…`) · tolerances **v1** (`d67ccdda…`) · canonicalization **v1** (`527cf87c…`) |
| Cycles | 1: 07:02:43–07:06:42Z · 2: 07:06:48–07:11:16Z · 3 (final): 07:11:21–07:16:00Z · green streak 3 · red runs `[]` |
| Evidence commit | `tp-run/mongodb-20260901T205236Z--parallel-run-v2` @ `2443d6f5bcf6f93445a2ee14226edb677af943a4` |
| Superseded watermark | `0150de08` (`--parallel-run` @ `3279c93b`, load 05:25–05:28Z, cycles 05:30–05:44Z) — same source watermark, pre-fix code head; not relied upon |

## 2. Approved mapping spec

| Version | Status | Where |
|---|---|---|
| v1.0 | frozen at STOP B (`05_decisions.md` row 8) | `.migration/03_mapping_spec.md` / `.json` |
| v1.0.1 | grading-only amendment, `05_decisions.md` **row 9**: `codes` key.source `[CODE_TYPE, CODE_VAL]` → scalar `CODE_TYPE||':'||CODE_VAL`; target `_key`, shapes, tolerances and data unchanged; pre-authorized per STOP A | same files, `"version": "v1.0.1"`, sha256 `57de55f2…` byte-identical at every attested head, at `0150de08` and at `74ecd69e` |

No tolerance, mapping-shape or canonicalization change was made after STOP B. Every "amendment" note in §6 is
recorded as *described, not applied*.

## 3. Coverage table — 44/44 census objects

`M` mapped · `R` rewritten · `A` absorbed · `X` excluded. "Wave report line" = the report and the section that attests
the object at the merged head; the final cycle-3 tallies are in §5.

| # | Source object | Unit | Target | Wave report line |
|---|---|---|---|---|
| 1 | `CODES` (32) | U0 | `codes` (`_key`) | wave0 §0 U0 row, §3.19 (T1 3/3, T2 14/14, T3 104/104) |
| 2 | `TENANTS` (69) | U0 | `tenants` | wave0 §0 U0 row |
| 3 | `PLANS` (3) | U0 | `plans` | wave0 §0 U0 row, §3.20 |
| 4 | `CUSTOMER_MASTER` (25,000) | U1 | `customers` | wave1 (part1) §0 U1 row (T3 33,333 incl. 8,333 `attributes`) |
| 5 | `ENTITY_ATTR_VALUE` (8,333) | U1 | `customers.attributes[]` | wave1 (part1) §0 U1 row |
| 6 | `CUSTOMER_MASTER_HIST` (0) | U1 | `customers_history` (empty) | wave1 (part1) §0 U1 row |
| 7 | `INVOICE_HEADER` (18,750) | U2 | `invoices` | wave1 (part1-u2) §0 U2 row (T3 168,713/168,713) |
| 8 | `INVOICE_LINE` (150,000) | U2 | `invoices.lines[]` (149,963) + Q.`invoice_feed_orphan_lines` (37) | wave1 (part1-u2) §0 U2 row, §2 quarantine set 37/37 |
| 9 | pg `documents` (2,000) | U3 | `documents` | wave1 (`--wave1-recon`) U3 row (T3 16,260) |
| 10 | pg `document_versions` (13,876) | U3 | `documents.versions[]` | wave1 (`--wave1-recon`) U3 row |
| 11 | pg `document_snapshots` (390) | U3 | `document_snapshots` (384) + Q.`orphan_document_snapshots` (6) | wave1 (`--wave1-recon`) U3 row |
| 12 | ddb `otterworks-file-metadata` `ns=demo` (10,000) | U4 | `files` | wave1 (`--wave1-recon`) U4 row pass 2 (T3 10,000/10,000) |
| 13 | `SUBSCRIPTIONS` (69) | U5 | `subscriptions` | wave2a §0 U5 row (T1 11/11, T2 53/53, T3 902/902) |
| 14 | `SUBSCRIPTIONS_HIST` (0) | U5 | `subscriptions_history` (empty) | wave2a §0 U5 row |
| 15 | `USAGE_EVENTS` (814) | U5 | `usage_events` | wave2a §0 U5 row, §4 |
| 16 | `RATING_PERIODS` (3) | U5 | `rating_periods` | wave2a §0 U5 row |
| 17 | `RATING_RESULTS` (3) | U5 | `rating_periods.results[]` | wave2a §0 U5 row (embed 3 graded) |
| 18 | `INVOICES` (3) | U5 | `billing_invoices` | wave2a §0 U5 row |
| 19 | `INVOICE_LINES` (2) | U5 | `billing_invoices.lines[]` | wave2a §0 U5 row (embed 2 graded) |
| 20 | `CREDIT_NOTES` (5) | U5 | `credit_notes` | wave2a §0 U5 row |
| 21 | `DUNNING_ATTEMPTS` (1) | U5 | `dunning_attempts` | wave2a §0 U5 row |
| 22 | `NOTIFICATIONS` (1) | U5 | `notifications` | wave2a §0 U5 row |
| 23 | `BILLING_AUDIT_LOG` (0 at census, 1 live observer row) | U5 | `billing_audit_log` (TTL 90 d) | wave2a §0 U5 row (reload after observer drift); wave2b §2.2 1/1; wave3 §0 table |
| 24 | `FIXTURE_META` | — | **X** excluded (no application reader) | census only; read as a stability probe in every report |
| 25 | `PKG_OW_UTIL` | U6 | `ow_billing/util.py` | wave2b §0 U6 row, §2.1 (T4 5/5 via PLANS-00x) |
| 26 | `PKG_PLANS` | U6 | `ow_billing/plans.py` | wave2b §0 U6 row, §2.1 |
| 27 | `PKG_RATING` | U7 | `ow_billing/rating.py` | wave2b §0 U7 row, §2.2 (T4 8/8) |
| 28 | `PKG_INVOICING` | U8 | `ow_billing/invoicing.py` | wave3 §0 U8 row, App. A §2.1 (T4 6/6); fix pass `fix_pass.md` (T4 6/6 at `7791a93e`, 26/26 probes, F-U8-1 closed) |
| 29 | `PKG_DUNNING` | U9 | `ow_billing/dunning.py`, `jobs.py`, `/api/dunning/*` | wave3 §0 U9 row, App. A §2.2 (T4 5/5) |
| 30 | `TRG_CUSTOMER_MASTER_SEQ` | U1 | `counters` + write path | wave1 (part1) U1 row (`counters` == `USER_SEQUENCES`) |
| 31 | `TRG_CUSTOMER_MASTER_HIST` | U1 | `customers_history` append | wave1 (part1) U1 row (write-path smoke) |
| 32 | `TRG_ENTITY_ATTR_VALUE_SEQ` | U1 | `counters` | wave1 (part1) U1 row |
| 33 | `TRG_SUBSCRIPTIONS_HIST` | U6 | `subscriptions_history` append | wave2b §2.1 `sp_change_plan` (8 paths) |
| 34 | `TRG_SUB_NO_UNCANCEL` | U6 | guard in `sp_change_plan` | wave2b §2.1 (cancelled row stays 30) |
| 35 | `TRG_USAGE_EVENTS_CHECK` | U5 | `$jsonSchema` on `usage_events` | wave2a §0 U5 row (validator cloned/verified) |
| 36 | `TRG_BILLING_AUDIT_LOG_ID` | U6 | `log_id` from `counters` (`seq_billing_audit_log`, single `util.log_msg` contract) | wave2b §2.1 audit log; fix pass `fix_pass.md` (F-X-1 closed: ids `[3..8]` monotonic across util→rating→invoicing) |
| 37 | `SEQ_CUSTOMER_MASTER` | U1 | `counters` doc (125000) | wave1 §3 `counters` 125000/1/11001 |
| 38 | `SEQ_CUSTOMER_MASTER_HIST`, `SEQ_ENTITY_ATTR_VALUE` | U1 | `counters` docs | wave1 §3 |
| 39 | `SEQ_SUBSCRIPTIONS_HIST`, `SEQ_BILLING_AUDIT_LOG` | U1 (seed rows added by U8-fix, row 19) | `counters` docs `seq_subscriptions_hist` 1, `seq_billing_audit_log` 2 (`== USER_SEQUENCES.LAST_NUMBER`) | fix pass `fix_pass.md` (`load_report.counters.json`, 5/5); parallel-run v2 `evidence/fix_acceptance_probe.txt` (`counters_eq_user_sequences: true`) |
| 40 | `JOB_NIGHTLY_DUNNING` (disabled) | U9 | `ow_billing/jobs.py`, env-gated, shipped disabled | wave3 App. A §2.2 / ledger U9 "never scheduled/activated" |
| 41 | `JOB_PURGE_AUDIT_LOG` (disabled) | U5 | TTL index `billing_audit_log.logged_at` | wave2a §0 U5 row (TTL option verified, expiry unobserved) |
| 42 | 25 indexes / 44 constraints | per unit | `_id`, unique indexes, app-side FK checks, orphan classes | every report's baseline "index specs equal" probe; wave1 §3 orphan sets |
| 43 | `app.py` 13 routes → `billing.*` | U6–U9 | **partially rewired** — see §7 | wave2b §2.1 HTTP, wave3 App. A §2.3 (informational: `/api/invoices/*` still Postgres) |
| 44 | `reports.py` RPT-114 (`STATUS_SQL`, `LINE_SQL`, `BALANCES_SQL`) | U1/U2 | aggregation pipelines on `invoices`+`codes`, `customers` | wave1 (part1-u2) §2 app-level replays (3 + 12 rows, balances `(25000, 39799450.31, 7330214.66)`) |

Totals: 23 M · 15 R · 5 A · 1 X = 44. Mapped collections in the count guard: 18/18. Golden `counters` at the watermark: 5 docs
(`seq_billing_audit_log` 2, `seq_customer_master` 125000, `seq_customer_master_hist` 1, `seq_entity_attr_value` 11001,
`seq_subscriptions_hist` 1), each Int64 and equal to `USER_SEQUENCES.LAST_NUMBER`.

## 4. Wave reports (independent LIVE recon, one per wave)

| Wave | Units | Report | Verdict |
|---|---|---|---|
| 0 | U0 | `tp-run/mongodb-20260901T205236Z--wave0-recon-part1:.migration/recon/wave_reports/wave0.md` (LIVE gate @ `892eb88a`: `--wave0-recon`) | PASS |
| 1 | U1, U2, U3, U4 | `tp-run/mongodb-20260901T205236Z--wave1-recon-part1-u2:.migration/recon/wave_reports/wave1.md` (U2 pass 3 @ `9e73ffea`; U1 @ `c5baa80a` in `--wave1-recon-part1`; U3 @ `dfa5e978`, U4 @ `3420f475` in `--wave1-recon`) | PASS |
| 2a | U5 | `tp-run/mongodb-20260901T205236Z--wave2a-recon-part1:.migration/recon/wave_reports/wave2a.md` (@ `1aefd226`) | PASS |
| 2b | U6, U7 | `tp-run/mongodb-20260901T205236Z--wave2b-recon-part1:.migration/recon/wave_reports/wave2b.md` (@ `f463577b`, `f05741f3`); probe bundle **committed** at `tp-run/mongodb-20260901T205236Z--wave2b-recon-part1:.migration/recon/wave_reports/wave2b_probes/{U6,U7}/` (branch head `59246e76`: `gate/{result.json,report.md,recon.summary.md}`, `tier4_replay.json` / `tier4_provenance.json`, `probe_u6.py`/`probe_u7.py`, `probes.json`, load reports, pre/post-reload fingerprints) | PASS with findings |
| 3 | U8, U9 | `tp-run/mongodb-20260901T205236Z--wave3-recon-part1:.migration/recon/wave_reports/wave3.md` (@ `0024b45e`, `9f67ec79`; LIVE gate in App. A / `--wave3-recon`) | PASS with findings |
| fix pass | U8 (+ U5/U6/U7 regression) | `tp-run/mongodb-20260901T205236Z--fix-recon:.migration/recon/wave_reports/fix_pass.md` (@ `7791a93e`; branch head `63a17306`; evidence `fix_pass_evidence/{U5,U6,U7,U8}/gate/`, `U8/gate_run2/` idempotency, `probes.py` + `probes_current_head.json` 26/26, `load_report.counters.json`, `source_pre/post.json` byte-identical, `target_pre/post.json` golden sha-identical, `fix_pass.recon.json` schema-validated) | PASS — closes F-U8-1, F-X-1 |

Wave closes: `05_decisions.md` rows 10–16; fix-pass merge row 20. Per-unit merged status and "unverified paths": `04_progress.md`.

## 5. Parallel run and final recon at the watermark

| Artefact | Path (branch `tp-run/mongodb-20260901T205236Z--parallel-run-v2` @ `2443d6f5`) |
|---|---|
| Parallel-run ledger (v2, CURRENT) | `.migration/recon/parallel_run/evidence_log.md` (+ machine-readable twin `evidence_log.json`) |
| Final recon at the watermark | `.migration/recon/parallel_run/final_recon_at_watermark.md` |
| Watermark source reads | `evidence/watermark/{source_pass1,source_pass2}.json`, `load_start_utc.txt` |
| Full-estate load from `74ecd69e` | `evidence/load/U0..U9.load_report.json`, `U0..U9.log`, `load_summary.jsonl`, `load.console.log` |
| Cycles 1–3 | `evidence/cycle{1,2,3}/U0..U9/gate/{result.json,report.md,recon.summary.md[,tier4_provenance.json,tier4_replay.json]}`, `guards.json`, `source_pre.json`, `source_post.json`, `steps.jsonl`, `cycle{1,2,3}.console.log` |
| Fix-pass acceptance probe at the watermark | `evidence/fix_acceptance_probe.txt` (read-only, after cycle 3; informational) |
| Tools | `.migration/recon/parallel_run/tools/{cycle.sh,full_load.sh,guards.py,source_check.py,subset.py,build_evidence.py}` |

The v1 ledger on `--parallel-run` @ `3279c93b` (watermark `0150de08`) is superseded and kept only as history.

Final-cycle tallies (cycle 3, byte-identical modulo `generated_at` to cycles 1–2 and to the wave-report / fix-pass tallies):

| Unit | T1 | T2 | T3 (full diff) | T4 | Verdict |
|---|---|---|---|---|---|
| U0 | 3 | 14 | 104 | — | PASS |
| U1 | 3 | 313 | 33,333 | — | PASS |
| U2 | 2 | 9 | 168,713 | — | PASS |
| U3 | 3 | 18 | 16,260 | — | PASS |
| U4 | 1 | 12 | 10,000 | — | PASS |
| U5 | 11 | 53 | 902 | — | PASS |
| U6 | 14 | 67 | 1,006 | 5 | PASS |
| U7 | 5 | 23 | 892 | 8 | PASS |
| U8 | 8 | 36 | 902 | 6 | PASS |
| U9 | 7 | 39 | 145 | 5 | PASS |

Guards: ns-scoped count guard 18/18 · quarantine ceiling ≤0.5 % (U1 0.324 %, U2 0.197 %, U3 0.252 %, others 0) · source
pre == post on every cycle (8/8 reads identical; `BILLING_AUDIT_LOG` 1, `SEQ_BILLING_AUDIT_LOG` 2 throughout) · quarantine DB =
exactly the 4 declared classes (`dirty_signup_dt` 50, `bad_csv_list` 31, `invoice_feed_orphan_lines` 37,
`orphan_document_snapshots` 6) · 0 UNGRADED warnings · Tier-4 provenance `oracle_source_sha 0d326cad…d55`,
`transcripts_match: true` in every cycle. Acceptance probe after cycle 3: golden `counters` 5/5 == `USER_SEQUENCES.LAST_NUMBER`;
every `billing_invoices.lines[].invoice_id == parent _id` on golden (3 invoices / 2 lines) and on all replay clones after Tier-4
(`replay_u8` 6 / 17 / 0 missing).

## 6. Open-issues list with dispositions

Every "described only / advisory / recommended, not applied" note from the wave reports and `05_decisions.md` rows 10–16,
plus every carried finding. Dispositions: `accepted-as-is` · `deferred-to-decommission` · `needs-STOP-C-line`; items fixed
and re-gated by the fix pass (rows 19–20) are marked `CLOSED` with their evidence. Exactly two items carry
`needs-STOP-C-line`: F-U8-2 / F-U7-1 (§H.3) and the partial application scope (§H.2).

| Id | Source | Item | Disposition | Rationale |
|---|---|---|---|---|
| F-U8-1 | wave3 §3; dec. 15, 19, 20 | `sp_issue_invoice` rebuilt `billing_invoices.lines[]` without the mapped `invoice_id` (code at `0150de08`) | **CLOSED** (fixed + re-gated) | PR #1457 @ `7791a93e` merged `5fe2af81`; `invoicing.py` rebuild emits `invoice_id` per line, `tests/test_invoicing.py` covers it. Independent LIVE re-gate `--fix-recon:…/fix_pass.md`: U8 T1 8/8, T2 36/36, T3 902/902, **T4 6/6** (INVOICE-001…006), idempotent rerun identical (`U8/gate_run2/`), probes `replay_u8_billing_invoices` 6 invoices / 17 rebuilt lines / 0 missing `invoice_id`. Re-confirmed at watermark `74ecd69e` in `--parallel-run-v2` cycles 1–3 (U8 PASS ×3) and `evidence/fix_acceptance_probe.txt` |
| F-X-1 (incl. F-U7-3, dec. 14 (2)) | wave2b §3, wave3 §3; dec. 14/15, 19, 20 | Three `log_msg` call sites carried two `counters` contracts (`SEQ_BILLING_AUDIT_LOG`/`value` vs `seq_billing_audit_log`/`seq`); golden `counters` had no audit-sequence seed | **CLOSED** (fixed + re-gated) | Same PR: `rating.log_msg` and `invoicing.log_msg` are thin delegates to `util.log_msg`; `plans`/`dunning` call it directly; unseeded counter raises `LookupError` (loud, never self-seeds). Seed: `load_u1.py --counters-only` (`$max` upsert, never rewinds) under the one-off write granted by row 19 → golden `counters` = 5 docs each `seq == USER_SEQUENCES.LAST_NUMBER` (`seq_billing_audit_log` 2, `seq_subscriptions_hist` 1, …), shape `{_id, seq:Int64, source_sequence, ns}`; no legacy `SEQ_BILLING_AUDIT_LOG`/`value` doc anywhere. Fix-pass dynamic probe: util→rating→invoicing×2 from seed 2 returned ids `[3,4,5,6,7,8]`, monotonic, no collision. Re-confirmed at `74ecd69e`: `fix_acceptance_probe.txt` `counters_eq_user_sequences: true`; U6/U7/U8/U9 Tier-4 PASS ×3 cycles on the single contract |
| F-U8-2 / F-U7-1 | wave2b §3, wave3 §3; dec. 15, 19 | Finalising/issuing a fixture-seeded period (tenant 1, ids `4000…01/02/03` ≠ md5) succeeds on Mongo where Oracle raises `ORA-02291` | **needs-STOP-C-line** → runbook **§H.3** | Behaviour decision (keep Oracle's error vs loader-side id normalisation) is the customer's; affects exactly 3 legacy periods. Carried by human decision (row 19); not re-probed in the fix pass; unchanged at `74ecd69e` |
| F-U6-1 | wave2b §3 | `util.f_str2dt` stricter than `TO_DATE('DD-MON-YY')`; no PL/SQL caller outside `PKG_OW_UTIL` | accepted-as-is | Dead branch in the estate; declared in the unit contract |
| F-U6-2 | wave2b §3 | Repeated identical plan-change → HTTP 500 (legacy surfaces ORA-00001 as 500 too) | accepted-as-is | Parity with legacy behaviour |
| F-U7-2 | wave2b §3; dec. 14 (1) | `billing_audit_log` excluded from U7 `GRADED_SOURCES` T1–T3; graded independently 1/1 equal; optional re-inclusion | accepted-as-is | Coverage exists via reviewer probe + U5/U6 gates; re-inclusion is additive and grading-only, not required for the verdict |
| F-U7-3 | wave2b §3 | `rating.py` duplicated `f_md5_uuid`/`log_msg` from `util.py` | CLOSED (folded into F-X-1) | `rating.log_msg` now delegates to `util.log_msg` (fix pass, static check) |
| F-FIX-2 | fix_pass.md; parallel-run v2 | U6 replay-clone seeder writes `LAST_NUMBER−1` whereas U1/U7/U8 write `LAST_NUMBER` (first Mongo-issued `log_id` differs by one between clone and golden) | accepted-as-is | Clone-only (`replay_u6_counters`); golden seed is `LAST_NUMBER`; no collision possible. Consequence for production: the first post-cutover `log_id` is `LAST_NUMBER+1` = 3 (Oracle would have issued 2) — a gap of one id, recorded in runbook §E.4/E.5 |
| F-U8-3, F-U9-1, X-1, F-XU-1 | wave3 §3, wave1 §3 | Informational parity notes (autonomous audit row; sorted tenant iteration; fixture `INVOICES.PERIOD_ID` cross-tenant quirk; invoice tenants not in `tenants` both sides) | accepted-as-is | Source quirks mirrored exactly |
| F-U9-2 | wave3 §3; parallel-run v2 "carried" | `/api/dunning/*`, `/api/plans*`, `/api/tenants/*`, `/api/reports/*` and `jobs.py` need `MONGODB_ATLAS_URI` at request time; no deployment path supplies it to `legacy-billing` today | accepted-as-is (becomes runbook step §D.5, executed by CUSTOMER) | Deployment wiring is a customer cutover step, not a code gap and not a decision |
| F-U4-1 | wave1 §5; dec. 12 (2), 16 (b) | `files.size_bytes` stored int32 vs declared long (value-exact); Tier-2 BSON `$type` histogram per declared `bson_type` would make width drift gradable | accepted-as-is | Grading-only harness enhancement; T3 full diff already covers values. Backlog for the harness, not for this cutover |
| F-U2-2 | wave1 U2 row; ledger | U2 loader drop+reinsert without staging swap | accepted-as-is | Relevant only to re-loads; the watermark load is final and frozen. Recorded as a runbook constraint: no re-load after freeze |
| dec. 12 (1) / 16 (a) | wave1 §5 | Pin the quarantine-ceiling denominator wording (root rows of the unit, all root collections summed) | accepted-as-is | Documentation clarification of `02_tolerances`; the final recon computed it that way (U3 6/2,384 = 0.252 %) and all units pass under either reading |
| dec. 14 (2) | wave2b §4 (2) | Declare the `counters` document contract in the mapping spec | accepted-as-is (contract now single in code; spec text unchanged) | The operative contract `{_id: "seq_<oracle_sequence lower>", seq: Int64, source_sequence, ns}` is enforced by `util.log_msg`/`plans.py` and verified by the fix pass; mapping v1.0.1 text is not amended (no shape change; documenting it is a v1.0.x grading-only clarification that may be applied later) |
| dec. 15 (1) | wave3 §4 (1) | Post-Tier-4 Tier-3 diff of the clone vs an Oracle replay (would have caught F-U8-1 mechanically) | deferred-to-decommission | Harness backlog; irrelevant once Oracle is retired |
| dec. 15 (2) | wave3 §4 (2) | `--reset-after` in U8's replay driver (false Tier-1 alarms on re-gate) | deferred-to-decommission | Harness backlog; no effect on parity |
| wave2a §6 | wave2a | Reviewer probes must not invoke `PKG_*` PL/SQL against the live fixture; `billing_audit_log` expected 1 not 0; spec text `units >= 0` vs enforced `> 0`; `counters` seeds from `USER_SEQUENCES` at cutover | accepted-as-is (first three) · CLOSED (seed — done by the F-X-1 fix, part of the U1 loader) | Process/documentation notes; the seed is now part of every full-estate load (`load_u1.py`), so no separate cutover step is needed |
| U0 wave0 | ledger U0 row | No Tier-4 ops for U0; `plans.tier` DECODE unpersisted, graded by consuming unit | accepted-as-is | Reference data; consumed and graded by U6/U7 |
| U1/U2/U3/U4 ledger | `04_progress.md` | Write-path smoke only for `customer_writes.py`; `derived_ungraded` twins unit-tested; RPT-114 checked under Flask test client not gunicorn; U3 `state_b64` never decoded; U4 file-service (Rust) read/write path against `files` not exercised; `HeadObject` path untested | accepted-as-is for data parity · **needs-STOP-C-line** for scope → runbook **§H.2 (d), (e)** (document-service and file-service are **not** repointed) | Data-layer parity is proven; application repoint for documents/files is out of the current scope by human decision (row 19) |
| Application scope (spec row 43) | wave2b §2.1, wave3 App. A §2.3; dec. 18, 19 | 10 of 13 `app.py` routes still call Postgres `billing.*`; rating and invoicing have no Mongo HTTP route | **needs-STOP-C-line** → runbook **§H.2 (a), (b), (c)** | Partial application scope carried forward as explicit STOP C lines by human decision (row 19); unchanged at `74ecd69e` (`app.py` routes not touched by the fix pass) |
| U5/U6/U9 ledger | `04_progress.md` | TTL expiry unobserved; concurrency paths unit-tested only; `JOB_NIGHTLY_DUNNING` replacement never scheduled; Flask routes carry no auth (matches legacy) | accepted-as-is | Verified at the level the legacy estate itself provides |

## 7. Stored-procedure track (Tier-4 parity per package)

Tier-4 source side for U7/U8/U9 is **recorded Oracle transcripts** (`procs/oracle/transcripts/{rating,invoicing,dunning}`)
whose `ORACLE_SOURCE_SHA 0d326cad54d94cd64e8abb53585b37436eaad2193fdc15ba3596fbb8db3f0d55` equals the sha256 of the live
`USER_SOURCE` for the five packages (`transcripts_match: true`, `--parallel-run-v2:…/evidence/cycle3/U{7,8,9}/gate/tier4_provenance.json`).
U6 Tier-4 is `evidence/cycle3/U6/gate/tier4_replay.json` against the same source. All five packages are `VALID` in
`USER_OBJECTS`; live bodies equal the checked-in `db/oracle/**/*.sql` (whitespace-normalised). Tier-4 pass counts below are
the cycle-3 (final) values at `74ecd69e`, identical in cycles 1–2 and to the wave / fix-pass reports.

| Package | Port | Transcripts | Tier-4 (final cycle) | Independent probes | Legacy still read by any code path? |
|---|---|---|---|---|---|
| `PKG_OW_UTIL` | `ow_billing/util.py` | exercised through PLANS-001…005 (no own transcript ids) | 5/5 (via U6) | wave2b §2.1: `f_md5_uuid` 7/7, `f_code_desc` 32+2 branches, `f_dt2str` ok, `f_str2dt` 10/15 (F-U6-1) | **Yes** — `app.py` `/`, `/plans`, `/plans/<t>/entitlement`, `/plans/<t>/change`, `/health` still call Postgres `billing.*` (spec row 43, calibration routes). Mongo equivalents live at `/api/plans`, `/api/tenants/<t>/entitlement`, `/api/tenants/<t>/plan-change` |
| `PKG_PLANS` | `ow_billing/plans.py` | PLANS-001…005 | 5/5 | wave2b §2.1: `fn_list_plans` full parity, `fn_entitlement` 414 ops, `sp_change_plan` 8 paths, HTTP 71/72 | same as above |
| `PKG_RATING` | `ow_billing/rating.py` | RATING-001…008 | 8/8 | wave2b §2.2: `fn_usage_rating` 552 ops 0 mismatches, `fn_usage_summary` 306 rows, `sp_finalize_rating` 5 paths (F-U7-1) | **Yes** — `app.py` `/api/rating/preview`, `/api/rating/finalize` still call Postgres `billing.*`; **no Mongo HTTP route exists** for rating (Python module only) |
| `PKG_INVOICING` | `ow_billing/invoicing.py` | INVOICE-001…006 | 6/6 | wave3 App. A §2.1: `fn_invoice_preview` 280 ops, `sp_issue_invoice` 10 paths, `fn_invoice_lines` 4 (76/85 at `0024b45e`; F-U8-1 ×8, F-U8-2 ×1); fix pass at `7791a93e`: T4 6/6, 26/26 probes, `lines[].invoice_id` 17/17 on rebuilt lines (F-U8-1 closed; F-U8-2 remains a §H.3 line) | **Yes** — `app.py` `/api/invoices/<t>/preview`, `/api/invoices/<t>/issue`, `/api/invoices/<id>/lines` still call Postgres `billing.*`; **no Mongo HTTP route exists** for invoicing |
| `PKG_DUNNING` | `ow_billing/dunning.py`, `jobs.py`, `/api/dunning/*` | DUNNING-001…005 | 5/5 | wave3 App. A §2.2: `fn_overdue_accounts` 16 as_of, `sp_schedule_dunning` 7 runs, `sp_suspend_overdue` 5 runs, routes 65/65 | No legacy read; Mongo routes exist. `JOB_NIGHTLY_DUNNING` replacement is env-gated (`OW_BILLING_JOB_NIGHTLY_DUNNING_ENABLED`) and never activated |

`reports.py` RPT-114 (`/api/reports/month-end`, `/api/reports/reconciliation`): Mongo-only via `MONGODB_ATLAS_URI`
(`oracle_connect`/`oracle_query` helpers remain in the file but no route calls them). `services/document-service` and
`services/file-service` contain no Mongo client: they still read Postgres and DynamoDB respectively.

## 8. Gap ledger (v1 gaps → v2 status)

| # | v1 gap (watermark `0150de08`) | v2 status | Evidence |
|---|---|---|---|
| 1 | F-U8-1 not fixed, not re-gated | **CLOSED** | PR #1457 @ `7791a93e` → merge `5fe2af81` (dec. 20); `tp-run/mongodb-20260901T205236Z--fix-recon:.migration/recon/wave_reports/fix_pass.md` (U8 T4 6/6, idempotent, probes 26/26, `fix_pass_evidence/U8/gate/`, `U8/gate_run2/`, `probe_lines_after_gate.json`); `--parallel-run-v2:.migration/recon/parallel_run/evidence/cycle{1,2,3}/U8/gate/result.json` PASS at `74ecd69e`; `evidence/fix_acceptance_probe.txt` |
| 2 | F-X-1 not consolidated; no audit/hist counter seed | **CLOSED** | same PR; `fix_pass_evidence/load_report.counters.json` (5/5 `seeded == oracle_last_number`, `advanced_preserved=[]`), `probes_current_head.json` (single contract, ids `[3..8]`); `--parallel-run-v2:…/evidence/load/U1.load_report.json` (counters 5) and `evidence/fix_acceptance_probe.txt` (`counters_eq_user_sequences: true`, no legacy `SEQ_*`/`value` docs); `04_progress.md` U1 register row |
| 3 | F-U8-2 / F-U7-1 undecided | **STOP C line** (runbook §H.3) | decision row 19 ("carry forward as explicit STOP C decision lines"); §6 row F-U8-2 / F-U7-1 |
| 4 | Wave-2b probe bundle machine-local | **CLOSED** | committed at `tp-run/mongodb-20260901T205236Z--wave2b-recon-part1:.migration/recon/wave_reports/wave2b_probes/{U6,U7}/` (head `59246e76`; 39 files: gate results, `tier4_replay.json`/`tier4_provenance.json`, `probe_u6.py`/`probe_u7.py`, `probes.json`, load reports, fingerprints) — see §4 wave 2b row |
| 5 | Application scope partial | **STOP C lines** (runbook §A.2, §H.2 (a)–(e)) | decision row 19; §6 rows "Application scope" and "U1/U2/U3/U4 ledger"; §7 column "Legacy still read by any code path?" |

No gap remains open: gaps 1, 2 and 4 are closed with committed evidence; gaps 3 and 5 are explicit STOP C decision lines
that the orchestrator must present (runbook §H). Hence **COMPLETE**. The independent audit and STOP C have not started;
this pack does not pre-empt either.
