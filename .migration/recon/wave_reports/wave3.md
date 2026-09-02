# Wave 3 — independent reconciliation report, Part 1 — re-attestation pass (U8, U9)

Run `tp-run/mongodb-20260901T205236Z` · mapping **v1.0** (run-branch `.migration/03_mapping_spec.json`, sha256
`57de55f24c241c51…`, self-declared `"version": "v1.0.1"`; byte-identical at both PR heads and at run-branch head
`1c03cce7`) · tolerances **v1** (`d67ccdda431baa5d…`) · canonicalization **v1** (`527cf87c699275bd…`) · target
`ow_tp_mongodb_205236` (quarantine `ow_tp_mongodb_205236_quarantine`) · secret `MONGODB_ATLAS_URI` (name only) ·
fixtures: Oracle `localhost:52521/FREEPDB1` user `ow_billing`, Postgres `localhost:5432/otterworks` schema
`otterworks_demo`, LocalStack DynamoDB `localhost:4566` table `otterworks-file-metadata` · manifest
`testdata/legacy/manifests/demo.json` sha256 `0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89`
(re-verified on the parent checkout `~/repos/otterworks`) · recon params `--seed 714559852 --param batch_no=85559852
--param source_ns=demo` · source-load cap 1 (one serial read-only Oracle connection at a time). Session: 2026-09-02
04:40 → 04:55 UTC, parent machine, separate clone `~/wave_recon/otterworks` (worktree `~/wave_recon/w3_part1_wt`
on branch `tp-run/mongodb-20260901T205236Z--wave3-recon-part1`). This session converted nothing in wave 3 and did not
read the children's diagnoses (`u8.recon.json`, `u9.recon.json`, `recon_report_u*.py`, `report.md`, `self_check.md`).
The parent checkout, its shells and the fixtures were not touched; nothing was written to the target.

## 0. Wave-close brief (one page)

**Wave verdict: PASS (carried).** Both wave-3 units are already **merged into the run branch**, and each PR branch's
*current* head is exactly the head the prior wave-3 LIVE recon re-loaded from and gated
(`tp-run/mongodb-20260901T205236Z--wave3-recon:.migration/recon/wave_reports/wave3.md`, commit `0f6490f3`,
2026-09-02 03:56 UTC — reproduced verbatim below as Appendix A). Per the wave instruction ("units whose PR is already
merged into the run branch: attest the merged head and carry the PASS from the prior wave report for that head"),
neither unit was re-graded and the LIVE gate window was not consumed; there are **no unmerged units** in this wave.

| Unit | PR | Current PR-branch head (attested) | Merge commit on run branch | Merged? | Carried verdict (source) |
|---|---|---|---|---|---|
| U8 `PKG_INVOICING` → `ow_billing.invoicing` (D9/D10), Tier-4 clone `replay_u8_*` (11 collections + counters) | #1447 | `0024b45ed39005012ca88669be4dc80565a3c994` | `1d7aa08b5d884c0c66fa3bcb4afa72f403870d05` | yes (`merge-base --is-ancestor`; second parent of the merge) | **PASS (with findings)** — prior LIVE gate @ `0024b45e` after reload from head: T1 8/8 · T2 36/36 · T3 902/902 full diff (embeds `results` 3 + `lines` 2) · T4 6/6 (INVOICE-001…006), 0 warnings; probes 76/85 (9 flags = F-U8-1 ×8, F-U8-2 ×1); run 1 on the child's pre-existing clone FAILed T1 (child's own `sp_issue_invoice` residue; Oracle re-counted twice → not drift) |
| U9 `PKG_DUNNING` → `ow_billing.dunning` (+ `/api/dunning/*`, `jobs.py`), Tier-4 clone `replay_u9_*` (7 collections + counters) | #1444 | `9f67ec79059fc25bd04d56d1891cd0851a9c47ee` | `24592b0b65a53456d22c8c4b670a3a6245c1e239` | yes (`merge-base --is-ancestor`; second parent of the merge) | **PASS** — prior LIVE gate @ `9f67ec79` on both the pre-existing clone and after reload from head: T1 7/7 · T2 39/39 · T3 145/145 full diff · T4 5/5 (DUNNING-001…005), 0 warnings; probes 65/65 |

Head verification (this session, `git fetch origin --prune` at 04:41 UTC): `origin/…--u8` = `0024b45e`, second parent
of `1d7aa08b`; `origin/…--u9` = `9f67ec79`, second parent of `24592b0b`; both ancestors of run-branch head `1c03cce7`
(wave-3 close commit `4356a4ae`). **Unit-owned files unchanged** between each head and `1c03cce7` (`git diff` over
the unit's own change-set vs its merge-base `080d6319` is empty except the shared ledger `.migration/04_progress.md`,
3 lines): U8 — `services/legacy-billing/app/ow_billing/invoicing.py`, `tests/test_invoicing.py`,
`scripts/tp_mongo/{load_u8,recon_report_u8}.py`, `.migration/recon_ext/recon_u8.py`, `.migration/recon/U8/**`; U9 —
`app/ow_billing/{dunning,jobs,routes}.py`, `app/app.py`, `tests/test_dunning.py`,
`scripts/tp_mongo/{load_replay_u9,recon_report_u9}.py`, `.migration/recon_ext/recon_u9.py`, `.migration/recon/U9/**`.
Evidence: `wave3_part1_reattest_evidence/attested_heads.json`.

**Cheap state check (no re-grade; one serial read-only Oracle connection per script: 14 `COUNT(*)` + `FIXTURE_META`
+ 2 sequence reads + `USER_SOURCE` reads ≈ 2 s, one 37-row orphan query ≈ 1 s; target reads only):** confirms the
carried PASS still describes the *current* target/fixture state (`source_counts.json`, `target_counts.json`,
`golden_vs_wave3_prefingerprint.json`, `quarantine_orphan_set_check.json`, `provenance_check.json`):

| Population | Source (fixture, 04:44:29Z) | Golden target | `replay_u8_*` clone | `replay_u9_*` clone | Prior LIVE report (03:56Z) |
|---|---|---|---|---|---|
| `TENANTS` / `tenants` · `PLANS` / `plans` | 69 · 3 | 69 · 3 | 69 · 3 | 69 · — | same |
| `SUBSCRIPTIONS` · `SUBSCRIPTIONS_HIST` | 69 · 0 | 69 · 0 | 69 · 0 | 69 · 0 | same |
| `USAGE_EVENTS` | 814 | 814 | 814 | — | 814 |
| `RATING_PERIODS` · `RATING_RESULTS`/Σ`results[]` | 3 · 3 | 3 · 3 | 3 · 3 | — | 3 · 3 |
| `INVOICES` · `INVOICE_LINES`/Σ`lines[]` | 3 · 2 | 3 · 2 | 3 · 2 | 3 · 2 | 3 · 2 |
| `CREDIT_NOTES` · `DUNNING_ATTEMPTS` · `NOTIFICATIONS` | 5 · 1 · 1 | 5 · 1 · 1 | 5 · 1 · 1 | — · 1 · 1 | same |
| `BILLING_AUDIT_LOG` | 1 (`log_id=1`, PLANS/fn_list_plans, 22:53:00) | 1 (`_id` 1) | 1 (`_id` 1) | 1 (`_id` 1) | 1 (the wave-0 observer row) |
| Clone canonical sha256 vs golden (11 U8 + 7 U9 collections) | — | — | **11/11 equal** | **7/7 equal** | equal after final reload |
| Counters | `SEQ_BILLING_AUDIT_LOG`=2, `SEQ_SUBSCRIPTIONS_HIST`=1 | shared `counters`: 3 U1 docs, **no** audit-seq doc | `{SEQ_BILLING_AUDIT_LOG: value 1, ns}` | `{seq_billing_audit_log: seq 1, seq_subscriptions_hist: seq 0}` | same (F-X-1 still open) |
| `FIXTURE_META.INITIALIZED_AT` | `2026-09-01 20:53:10.961888` | — | — | — | same |
| `PKG_OW_UTIL/PLANS/RATING/INVOICING/DUNNING` | `USER_OBJECTS` VALID ×5; live `PKG_INVOICING`/`PKG_DUNNING` bodies == checked-in `packages/04_pkg_invoicing.sql` / `05_pkg_dunning.sql` (whitespace-normalized); `PKG_OW_UTIL/PLANS/RATING` body sha256 identical to the wave-2b Part-1 reading | — | — | — | same |
| Tier-4 provenance | checked-in `db/oracle/**/*.sql` sha at `1c03cce7` = `0d326cad…` = `procs/oracle/transcripts/ORACLE_SOURCE_SHA` = all 11 `invoicing/*` + `dunning/*` transcripts' `oracle_source_sha` | | | | `0d326cad…` |
| Golden + quarantine vs wave-3 pre-fingerprint (23 collections, same recipe: canonical JSON sorted by `_id` + `\n`) | — | **22/23 byte-identical** incl. all 19 golden collections and indexes; the 1 delta is `quarantine.invoice_feed_orphan_lines` (see below) | | | 23/23 at 03:56Z |
| `*__staging` residue · quarantine (as sets) | — | none · `bad_csv_list` 31, `dirty_signup_dt` 50, `invoice_feed_orphan_lines` 37, `orphan_document_snapshots` 6 (U8/U9 declare none; expected 0 new == observed 0 new) | | | same |

The single post-attestation change on the target is **outside wave 3**: `ow_tp_mongodb_205236_quarantine.invoice_feed_orphan_lines`
(U2's class) has the same 37 documents but a refreshed `quarantined_at = 2026-09-02 04:05:10Z` — i.e. the **U2 resumed
loader** (PR #1432 @ `9e73ffea`, evidence commit `1c03cce7` at 04:17Z) re-ran idempotently after the wave-3 LIVE recon
closed (03:56Z). Verified as a SET against the source: the 37 `_id`s equal the 37 `INVOICE_LINE.LINE_ID`s of batch
`85559852` with no `INVOICE_HEADER` parent (`quarantine_orphan_set_check.json`, `set_equal: true`); golden `invoices`
(18750) and every other golden/quarantine collection are byte-identical to the 03:23Z pre-fingerprint. No effect on
U8/U9 (they neither read nor write that class); noted for the U2 re-attestation.

All else equal to the attested state: no source drift since the LIVE gate (audit-log count still 1, sequence still
2 → no later session invoked `PKG_*` PL/SQL against the fixture), both replay clones are exactly at the fixture
baseline as the prior session left them after its final reload from the heads, no post-attestation reload of U8/U9
is evident and none was needed → the carried PASSes stand. Unit tests at the run head (`test_invoicing.py` 11,
`test_dunning.py` 8): **19 passed** (0.20 s).

**Fixtures:** Oracle (`otterworks-oracle-billing-oracle-billing-1`), Postgres, LocalStack containers healthy (up ~8 h);
nothing restarted, reseeded or modified; nothing written to the target.

**Findings (carried, unchanged; none new; none blocking merge — both PRs are merged):** **F-U8-1** (medium, mapping
contract) `sp_issue_invoice` rebuilds `billing_invoices.lines[]` without the mapped `invoice_id` field — still present
in `invoicing.py` at the merged head (code byte-identical to `0024b45e`), so it is now a **post-merge, pre-cutover fix
item**; **F-U8-2** (medium, inherited U7 F-U7-1) Mongo issues invoices for the 3 fixture-seeded periods that Oracle
would refuse (`ORA-02291`); **F-X-1** (medium, cutover) three `log_msg` call sites with two incompatible `counters`
contracts, shared golden `counters` still has no audit-sequence doc (re-verified today: 3 U1 docs only); F-U8-3,
F-U9-1, F-U9-2, X-1 informational. Details and evidence in Appendix A §3.

**Grading-only amendments: none warranted** (unchanged from the prior report; its two driver-enhancement notes — a
post-Tier-4 Tier-3 diff of the clone, and a `--reset-after` in U8's driver — are backlog items, not tolerance changes;
not applied).

**Cost (this session, serial, parent machine):** U8 — 0 s gate (carried) · head/merge attestation `git` only ·
state check share of one 14-`COUNT` Oracle pass ≈ 1 s · target reads (11 clone + 11 golden canonical fingerprints)
≈ 20 s · unit tests 0.1 s. U9 — 0 s gate (carried) · state check share ≈ 1 s · target reads (7 + 7 fingerprints) ≈ 10 s ·
unit tests 0.1 s. Shared: 23-collection pre-fingerprint re-hash ≈ 4 min (target-side only, dominated by `customers`
25000 / `invoices` 18750 / `files` 10000), orphan-set query 1 s, provenance `USER_SOURCE` reads 1 s. **Oracle source
time ≈ 4 s total**; wall clock ≈ 15 min; LIVE gate window not consumed.

**Recommendation:** close wave 3 as PASS (carried) at the merged heads above. Carry F-U8-1 and F-X-1 onto the
pre-cutover fix list (F-U8-1 is a one-line change in `invoicing.py` + re-gate; F-X-1 needs one counter id/field and
one seed in golden `counters`); orchestrator to decide F-U8-2/F-U7-1 (loader-side id normalisation vs. keeping
Oracle's error).

---

## Appendix A — prior wave-3 LIVE report, reproduced verbatim

Source: `tp-run/mongodb-20260901T205236Z--wave3-recon:.migration/recon/wave_reports/wave3.md` at commit
`0f6490f369b87134a232e4e17bccd434c8405d0c` (2026-09-02 03:56:29 UTC). Its evidence tree
(`.migration/recon/wave_reports/wave3_evidence/{U8,U9,xunit}/…`) lives on that branch and is referenced, not copied.

# Wave 3 — independent reconciliation report (U8, U9)

Run `tp-run/mongodb-20260901T205236Z` · mapping **v1.0.1** · tolerances **v1** · canonicalization **v1** · target
`ow_tp_mongodb_205236` (quarantine `ow_tp_mongodb_205236_quarantine`) · secrets by NAME only (`MONGODB_ATLAS_URI`,
`OW_BILLING_FIXTURE_DSN`) · mode **LIVE** on the parent machine's canonical fixtures (Oracle `localhost:52521/FREEPDB1`
user `ow_billing`; manifest sha256 `0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89`;
`FIXTURE_META.INITIALIZED_AT = 2026-09-01 20:53:10.961888` before and after) · seed `714559852` · params
`batch_no=85559852 source_ns=demo` · harness `mongo-migration-plugin-6d021e15/0.2.1` (`recon selftest PASS: 9
canonicalization rules exercised`) · source-load cap 1 honoured (one Oracle connection at a time; gates, loaders and
probes strictly serial). Reviewer converted nothing in this wave and did not read the children's diagnoses
(`u8.recon.json`, `u9.recon.json`, `report.md`, `self_check.md`) before re-running. Fixtures were neither restarted nor
reseeded; the Oracle source was observed with **plain SQL only** (the `PKG_*` packages write `BILLING_AUDIT_LOG`).
Checkouts were detached git worktrees under `~/wave_recon/heads/{u8,u9}` at the exact PR heads; the parent checkout
was not touched.

## 0. Wave-close brief (one page)

| Unit | PR / head attested | Load state graded | Gate (LIVE, verbatim per-unit driver) | Probes | Verdict |
|---|---|---|---|---|---|
| **U8** `PKG_INVOICING` → `ow_billing.invoicing` (D9/D10), Tier-4 clone `replay_u8_*` (11 collections + counters) | PR #1447, branch `--u8` @ **`0024b45ed39005012ca88669be4dc80565a3c994`** (remote head re-verified after the run; `gh pr view` headRefOid identical) | pre-existing clone gated first → **FAIL** T1 `replay_u8_rating_periods` 6 docs vs 3 rows, Σ`results` 6 vs 3, `replay_u8_billing_invoices` 6 vs 3, Σ`lines` 17 vs 2 (= the child's own Tier-4 `sp_issue_invoice` residue, not source drift: Oracle re-counted 3/3/3/2 **twice**, stable); **re-loaded by me from this head** (`scripts/tp_mongo/load_u8.py`, 03:24:57→03:25:06Z), then gated | **PASS** T1 8/8 · T2 36/36 · T3 902/902 (full diff; embeds `results` 3 + `lines` 2 graded) · T4 6/6 (INVOICE-001…006; transcripts' `ORACLE_SOURCE_SHA` = live `USER_SOURCE`), 0 warnings | **76/85 ok**; the 9 flags are two findings: F-U8-1 (rebuilt `lines[]` drop the mapped `invoice_id` field, ×8) and F-U8-2 (inherited U7 divergence, ×1) — §3. All 280 preview ops, 10 `sp_issue_invoice` paths (headers, 5 lines, burn-down, audit) and 4 `fn_invoice_lines` calls equal the PL/SQL re-expression exactly | **PASS** (with findings; F-U8-1 should be fixed before cutover — one-line, orchestrator decides whether pre-merge) |
| **U9** `PKG_DUNNING` → `ow_billing.dunning` (+ `/api/dunning/*` routes, `jobs.py`), Tier-4 clone `replay_u9_*` (7 collections + counters) | PR #1444, branch `--u9` @ **`9f67ec79059fc25bd04d56d1891cd0851a9c47ee`** (remote head re-verified after the run) | pre-existing clone gated first → **PASS** (the U9 driver resets its mutable collections before/after each op, so no residue); **re-loaded anyway from this head** (`scripts/tp_mongo/load_replay_u9.py`, 03:27:08→03:27:13Z) and gated again → same result | **PASS** T1 7/7 · T2 39/39 · T3 145/145 (full diff) · T4 5/5 (DUNNING-001…005; `ORACLE_SOURCE_SHA` = live), 0 warnings — identical on both loads | **65/65 ok** (fn_overdue 16 as_of + outer-join/UNKNOWN + empty; scheduler 7 runs incl. SAT/SUN, swallow path, empty set; suspend 5 runs incl. `<=` boundary, idempotency, multi-sub + cancelled immunity, history/notification/audit) | **PASS** |
| **Cross-unit** | | | | 28/29 — the 1 flag is a **source quirk faithfully mirrored** (fixture invoices reference tenant 1's rating periods; identical in Oracle), not a defect. F-X-1 re-confirmed LIVE (§3) | **PASS** with findings |
| **Wave 3** | | | | | **PASS** |

- **Drift?** None on the source: `BILLING_AUDIT_LOG` = 1 row, `SEQ_BILLING_AUDIT_LOG.last_number` = 2,
  `SEQ_SUBSCRIPTIONS_HIST.last_number` = 1, all table counts (RATING_PERIODS 3, RATING_RESULTS 3, INVOICES 3,
  INVOICE_LINES 2, CREDIT_NOTES 5, DUNNING_ATTEMPTS 1, NOTIFICATIONS 1, SUBSCRIPTIONS 69, SUBSCRIPTIONS_HIST 0,
  USAGE_EVENTS 814, TENANTS 69, PLANS 3) and `FIXTURE_META` identical before, between and after every step. The
  U8 run-1 failure was **target-side replay residue** (U8's driver replays `sp_issue_invoice` for 3 tenants and
  does not reset); reloading from the head restored the baseline and the gate went green.
- **Golden untouched.** All 19 golden collections + 4 quarantine classes byte-identical to the wave pre-fingerprint
  (`wave3_evidence/xunit/golden_pre_fingerprint.json`, 23 collections) after every gate/probe/reload; quarantine
  compared as **sets**: `bad_csv_list` 31 · `dirty_signup_dt` 50 · `invoice_feed_orphan_lines` 37 ·
  `orphan_document_snapshots` 6 (U8/U9 declare no quarantine targets; expected 0 new, observed 0 new). Both clones
  were re-loaded from their heads at the end, so `replay_u8_*`/`replay_u9_*` sit at the fixture baseline.
- **App-level replay (plain SQL vs Python, all equal):** U8 `fn_invoice_preview` 70 tenants × 4 windows = **280 ops**
  × 5 rows × 7 columns compared *unrounded* (4 no-plan/NULL rows, 24 tax-exempt, 8 credit-capped, 4 full-credit, 120
  non-zero overage, 251 with an odd `tax/2` half-cent), `fn_invoice_lines` 3 invoices + unknown id, `sp_issue_invoice`
  10 paths against an independent PL/SQL simulation (§2.1); U9 `fn_overdue_accounts` 16 as_of values, `sp_schedule_dunning`
  7 runs, `sp_suspend_overdue` 5 runs (§2.2), plus the Flask routes `GET /api/dunning/overdue` (7 dates + default +
  400), `POST /api/dunning/schedule`, `POST /api/dunning/suspend` (+400) through the test client on the clone (§2.3).
  The golden `app.py` `/api/invoices/*` routes still target Postgres `billing.*` which does not exist on this fixture
  (U8 exposes no HTTP route — informational, out of U8's D10 scope).
- **Findings (none blocking the gate):** **F-U8-1** `sp_issue_invoice` rebuilds `lines[]` without the mapped
  `invoice_id` field (mapping v1.0.1 embeds `INVOICE_LINES.INVOICE_ID → lines.invoice_id`; the loader writes it, the
  port does not) — any Tier-3 run over a post-cutover-issued invoice would flag it; **F-U8-2** inherited U7 F-U7-1
  now has a business consequence: issuing tenant 1's Jan-2026 (fixture-seeded, non-md5 period id) **issues an invoice
  on Mongo where Oracle raises `ORA-02291` and issues nothing**; **F-X-1** (wave 2b) re-confirmed LIVE: U8 logs through
  `rating.log_msg` (`SEQ_BILLING_AUDIT_LOG`/`value`), U9 through `util.log_msg` (`seq_billing_audit_log`/`seq`) — on
  one store the two loggers allocate the same `log_id` and the second write dies with `DuplicateKeyError`; **F-U9-1**
  (informational) `sp_suspend_overdue` iterates tenants sorted (Oracle `DISTINCT` order is unspecified) — only audit
  row order can differ; **F-U8-3** (informational) failed issue (no covering subscription) leaves exactly one
  autonomous `RATING compute` audit row, as Oracle does.
- **Grading-only amendments: none warranted.** (Two notes for the orchestrator in §4, neither applied.)
- **Cost (serial, parent machine):** **U8** — gate run 1 ≈ 25 s (FAIL, Tier-1 counts + Tier-2/3 fetch) · two source
  re-counts 2 s · reload 9.3 s · authoritative gate ≈ 25 s (8 COUNT + 36 aggregates + full keyed fetch of 11 tables;
  6 transcript replays) · unit tests 0.13 s (11 passed) · probes **226 s × 3 runs** (≈ 320 SQL statements per run: 280
  preview + ~40 metadata; the per-op Oracle round trip dominates) · 3 extra reloads 28 s. ≈ 13 min source time.
  **U9** — gate run 1 ≈ 20 s · reload 5.6 s · authoritative gate ≈ 20 s (7 COUNT + 39 aggregates + full keyed fetch of
  7 tables; 5 transcript replays) · unit tests 0.14 s (8 passed) · probes 43 s (≈ 60 SQL statements) · 3 extra reloads
  17 s. ≈ 2 min source time. Cross-unit 30.5 s (7 SQL). Total wall clock ≈ 30 min under the cap of 1.
- **Recommendation:** merge PR #1444 (U9) at `9f67ec79`. Merge PR #1447 (U8) at `0024b45e` **or** require the
  one-line F-U8-1 fix (add `"invoice_id": invoice_id` to each rebuilt line) plus a re-gate first — the data
  equality is otherwise exact. Before cutover: consolidate the `counters` contract (F-X-1, now three call sites),
  and decide whether F-U8-2/F-U7-1 (Mongo issues invoices Oracle would refuse for the 3 fixture-seeded periods)
  is behaviour to keep or a loader-side id normalisation.

---

## 1. Gate invocations (verbatim per-unit drivers; harness `recon selftest` PASS)

```
# U8  (worktree ~/wave_recon/heads/u8 @ 0024b45e…)
python .migration/recon_ext/recon_u8.py --unit U8 --mapping .migration/03_mapping_spec.json \
  --tolerances .migration/02_tolerances.json --canonicalization .migration/canonicalization.json \
  --mode live --source-dsn-secret OW_BILLING_FIXTURE_DSN --target-uri-secret MONGODB_ATLAS_URI \
  --target-db ow_tp_mongodb_205236 --seed 714559852 --param batch_no=85559852 --param source_ns=demo --out <dir>
# U9  (worktree ~/wave_recon/heads/u9 @ 9f67ec79…)
python .migration/recon_ext/recon_u9.py  (same flags, --unit U9)
```

| Unit | Run | Load state | Result | Detail |
|---|---|---|---|---|
| U8 | 1 (03:24Z) | pre-existing `replay_u8_*` as left by the child | **FAIL** | T1: `rating_periods` 6 vs 3, `billing_invoices` 6 vs 3; embeds `results` 6 vs 3, `lines` 17 vs 2. Triage: Oracle `SELECT COUNT(*)` on the 6 U8 tables re-run twice → identical to baseline (`wave3_evidence/U8/drift_source_recount.txt`) ⇒ **target residue**, not drift (defect class: none — the child's driver replays `sp_issue_invoice` for tenants 9/4/6 and does not reset; the extra 3 invoices/periods and 15 lines are exactly those). |
| U8 | 2 (03:25Z) | reloaded from head `0024b45e` (`load_u8.py`, drop-and-recreate, validators + indexes copied, counter seeded from max `log_id`=1) | **PASS** | T1 8/8 · T2 36/36 · T3 902/902 · T4 6/6 · 0 warnings (`wave3_evidence/U8/gate/`). |
| U9 | 1 (03:26Z) | pre-existing `replay_u9_*` | **PASS** | T1 7/7 · T2 39/39 · T3 145/145 · T4 5/5 · 0 warnings. |
| U9 | 2 (03:27Z) | reloaded from head `9f67ec79` (`load_replay_u9.py`; counters `seq_billing_audit_log`=1, `seq_subscriptions_hist`=0) | **PASS** | identical tallies (`wave3_evidence/U9/gate/`). |

Transcript provenance (`tier4_provenance.json`, both units): `ORACLE_SOURCE_SHA
0d326cad54d94cd64e8abb53585b37436eaad2193fdc15ba3596fbb8db3f0d55` = sha256 of the live `USER_SOURCE` for the five
packages — the recorded transcripts were taken from the code that is running. Unit tests at the heads: U8 `11 passed`,
U9 `8 passed`.

## 2. Adversarial probes (scripts + JSON under `wave3_evidence/{U8,U9}/probe_u*.py`, `probes.json`, `xunit/cross_unit.py`)

Method: Oracle read with plain SQL; expectations for the mutating procedures come from **my own re-expression of the
PL/SQL** (SQL CTE for `compute_preview` reusing the wave-2b `compute_rating` re-expression; Python simulation of the
credit-note burn-down loop / dunning loops fed by the clone state read *before* each call). Each probe script was run
on a freshly reloaded clone; the clone (never the golden set) is the only thing mutated.

### 2.1 U8 — `PKG_INVOICING` (76/85; 9 flags = F-U8-1 ×8, F-U8-2 ×1)

| Group | Probes | Result |
|---|---|---|
| baseline | 11 clone collections canonical-sha-equal to golden (incl. `_id`); index specs/TTL equal; `usage_events` `$jsonSchema` validator cloned; only the 12 owned `replay_u8_*` collections exist; counter `{_id:SEQ_BILLING_AUDIT_LOG, value:Int64(1)}` = max `log_id` = `USER_SEQUENCES.last_number−1` | 5/5 |
| nulls / dupes | NULL counts per field source==target for `credit_notes`(3 cols), `billing_invoices`(6), `tenants`(3); no duplicate business ids, `_id==id` everywhere | 6/6 |
| embed | `lines[]` length distribution `{0:2, 2:1}` == `INVOICE_LINES` children per header; `(invoice, line_no)` unique; every embedded `invoice_id` == parent | 2/2 |
| boundary / dist / types | min/max `issued_at`, Σ total/tax/subtotal; credit-note Σremaining, min/max `issued_on`, distinct tenants, positive count; `status_cd` distribution {20:1, 40:2} (10/30 absent in data — recorded); `tax_exempt_yn` {N:63, Y:6}; money `Decimal128`, dates BSON date, `line_no` int | 5/5 |
| parity (reads) | `fn_invoice_preview` == SQL re-expression on **280 ops** (69 tenants + unknown × Feb/Jan/Mar/straddle), 5 rows × 7 cols, *exact unrounded* (`tax/2` half-cents preserved); `fn_invoice_lines` for all 3 invoices (2 with zero lines) + unknown id → `[]` | 2/2 |
| `sp_issue_invoice` (10 paths) | INVOICE-003 tenant 9 (two credit dates, credit > cap), INVOICE-004 tenant 4 (equal `issued_on` ties → id order), INVOICE-005 tenant 6 (re-issue of existing 60..03 → `DUP_VAL_ON_INDEX` UPDATE path keeps `issued_at`/tenant/period), tenant 3 (tax-exempt, full credit), tenant 2 (suspended sub + existing OVERDUE 60..01 → status 40→20, suspension factor), tenant 9 **again** (idempotency quirk: less credit → higher total, same ids, lines rebuilt), tenant 1 Feb-15..Mar-15, tenant 1 Jan (→ F-U8-2), unknown tenant and tenant 1 Dec-2025 (no covering subscription → `RatingIntegrityError` before any invoice write, credit notes untouched, no period residue, exactly one autonomous `RATING compute` audit row — Oracle: `ORA-01400` on `RATING_RESULTS.SUBSCRIPTION_ID NOT NULL`, same observable state). For each: header (id=md5(md5(tenant‖start)‖'invoice'), tenant, period, issued_at, subtotal, tax=2×round(tax/2), total, status 20) == simulation; 5 lines (ids md5(invoice‖n), types, descriptions, amounts, credit line = −credit_applied) == simulation; credit-note burn-down (oldest first, `GREATEST(remaining−v,0)`, running-counter quirk) == simulation; audit row `issued invoice=<id> total=<TO_CHAR(NVL(total,0))>` (Oracle `FM`-less `TO_CHAR` → leading `.` for <1, `0` for zero) with sequential `log_id`; rating period finalized | 50/50 semantic; **0/8 shape (F-U8-1)**; **0/1 F-U8-2** |
| post | after all issues: `_id==id`, line_no unique, status ⊆ {20,40}, no invoice for the unknown tenant; `remaining_amount` ∈ [0, amount], `Decimal128`; `log_id`s contiguous 1..n, `Int64`, `ns` set | 3/3 |
| golden | 23 golden+quarantine collections byte-identical; quarantine sets {31,50,37,6}; Oracle counts + `FIXTURE_META` unchanged | 3/3 |

### 2.2 U9 — `PKG_DUNNING` (65/65)

| Group | Probes | Result |
|---|---|---|
| baseline | 7 clone collections sha-equal to golden; indexes equal incl. unique `(invoice_id, attempt_no)` and the `UQ_NOTIFICATIONS` mirror; counters U6-shape `{seq_billing_audit_log:1, seq_subscriptions_hist:0}` == Oracle `last_number−1`; only owned collections | 5/5 |
| nulls / dupes / dist | NULL counts for `dunning_attempts`(3), `notifications`(2), `tenants`(2), `subscriptions`(3); no dup ids; distributions `tenants.status_cd` {10:68, 20:1}, `subscriptions.status_cd` {10:68, 20:1}, `invoices.status_cd` {20:1, 40:2}, `dunning_attempts.status_cd` {20:1}, `notifications.kind_cd` {2:1} | 13/13 |
| boundary / types | min/max `scheduled_for`/`attempt_no`; `sent_at` keeps `09:00:00.000000` (TIMESTAMP(6)→date); ints/dates typed; every `tenant_id`/`invoice_id` resolves | 3/3 |
| `fn_overdue_accounts` | == SQL on **16 as_of** values incl. `TO_CHAR(YYYYMMDD)` boundaries (02-01 vs 02-01 23:59:59 vs 02-02; 02-13/14), far past/future, time-of-day; outer join (invoice with missing tenant → `UNKNOWN`), `DECODE` default for status 30 → `UNKNOWN`; empty result → `[]`; `date` == midnight `datetime` | 4/4 |
| `sp_schedule_dunning` (7 runs) | Mon 03-02 (60..02 → attempt 2 after the fixture attempt 1, 60..01 → attempt 1); same day again → attempts 3/2 (no per-day dedupe, as Oracle); **Sat 03-07 → Mon 03-09; Sun 03-08 → Mon 03-09**; Fri no shift; as_of 2020 (status filter only); planted PK collision → swallowed for that invoice, other still scheduled, return 1, log `scheduled 1 attempts …`; empty set → 0 and `scheduled 0 attempts as of 10-MAR-26` still logged. Each run: inserted docs (id=md5(invoice‖attempt_no), tenant, invoice, `scheduled_for`, status 10, ns) == simulation, exactly one `DUNNING` audit row `scheduled N attempts as of DD-MON-YY`, `log_id == counter.seq`; afterwards `(invoice_id, attempt_no)` unique and contiguous 1..k | 14/14 |
| `sp_suspend_overdue` (5 runs) | as_of 02-26 (cutoff 02-12: only 60..01 qualifies, tenant 2 already 20 → nothing); **02-27 (cutoff == `issued_at` 02-13, `<=` boundary) → tenant 5 suspended**; rerun → idempotent (no dup notification/history); tenant 5 re-activated with 2 active + 1 cancelled sub, as_of 03-01 → both active suspended, cancelled untouched, new 03-01 notification, 02-27 one kept; as_of 02-14 → no candidates, no writes. Each run: tenants→20, active subs→20 with `suspended_on=TRUNC(as_of)`, `trg_subscriptions_hist` rows (OLD image, `UPD`, `hist_dt` `DD-MON-YY HH24:MI:SS`, `hist_id` from `seq_subscriptions_hist`, `_id==hist_id`), notification `id=md5(tenant‖'suspension'‖YYYY-MM-DD)`, `sent_at=TRUNC(as_of)`, kind 3; non-active subs untouched; one `suspended tenant=<id>` audit row per tenant | 21/21 |
| post / golden | `log_id`s contiguous, `_id==log_id`, all new rows `DUNNING`; golden/quarantine byte-identical; Oracle `DUNNING_ATTEMPTS` 1 / `NOTIFICATIONS` 1 / `SUBSCRIPTIONS_HIST` 0 / suspended tenants 1 / `FIXTURE_META` unchanged | 5/5 |

### 2.3 Cross-unit + app-level (28/29; the flag is a mirrored source quirk)

| Probe | Result |
|---|---|
| `codes` SET source==golden (32 rows, `code_type/code_val/code_desc`); every code U8/U9 write (INV_STATUS 20/40, TENANT_STATUS 10/20, DUN_STATUS 10, NOTIF_KIND 3, SUB_STATUS 10/20) exists | ok |
| golden refs resolve: `billing_invoices.{tenant_id,period_id}`, `credit_notes.tenant_id`, `dunning_attempts.{tenant_id,invoice_id}`, `notifications.tenant_id`, `subscriptions.{plan_id,tenant_id}`, `rating_periods.tenant_id`, `usage_events.tenant_id`; `results[].period_id == parent`; `tenants.id`/`plans.id`/`subscriptions.plan_id` SETs == Oracle | ok (12) |
| `billing_invoices.period_id` → period of the **same tenant** | **flag** — all 3 fixture invoices (tenants 2/5/6) point at tenant 1's periods 40..01/40..02. Identical in Oracle (`INVOICES.PERIOD_ID` has no tenant check) ⇒ source data quirk faithfully preserved, not a migration defect. |
| F-X-1 static: U8 `rating.AUDIT_SEQUENCE='SEQ_BILLING_AUDIT_LOG'` (`value`), U9 `util.SEQ_BILLING_AUDIT_LOG='seq_billing_audit_log'` (`seq`); golden `counters` has neither (`seq_customer_master`, `seq_customer_master_hist`, `seq_entity_attr_value` only) | ok (confirms finding) |
| F-X-1 **LIVE** (on `replay_u9_*`): U8-style `log_msg` then U9-style `log_msg` on one store → both compute `log_id=max+1`; second write → `DuplicateKeyError` (in the reverse order U8's `WHEN OTHERS` mirror swallows it silently and the row is lost). Audit doc shapes otherwise identical | ok (confirms finding) |
| Flask test client (`OW_BILLING_COLLECTION_PREFIX=replay_u9_`): `GET /api/dunning/overdue?as_of=` 7 dates == Oracle SQL (money `'161.29'` strings, order `issued_at,id`); default as_of 2026-02-28 → 2 rows; invalid → 400 `{detail:'invalid as_of'}`; `POST /api/dunning/schedule {as_of}` → `{status:scheduled, scheduled:2}` + 2 docs; `POST /api/dunning/suspend {as_of:2026-02-27}` → `{status:suspended, tenant_ids:[tenant 5]}` + tenant 5 → 20; bad date → 400 | ok (6) |
| golden `app.py` `/api/invoices/*` still call Postgres `billing.fn_invoice_preview/sp_issue_invoice/fn_invoice_lines` (schema absent on this fixture) — U8 has no Mongo HTTP route | informational |
| golden + quarantine byte-identical after the whole wave | ok |

## 3. Findings

| Id | Unit | Severity | What | Evidence | Disposition |
|---|---|---|---|---|---|
| **F-U8-1** | U8 | medium (mapping contract) | `sp_issue_invoice` rebuilds `billing_invoices.lines[]` with keys `{id, line_no, line_type, description, amount}` — the mapped `invoice_id` (`INVOICE_LINES.INVOICE_ID → lines.invoice_id`, mapping v1.0.1 embed field 2) is **absent**. Loader-embedded lines carry it; every invoice issued by the port does not. Tier-3 over any post-cutover-issued invoice would flag `lines[].invoice_id` NULL≠value; readers filtering on `lines.invoice_id` miss rebuilt lines. Values/amounts are otherwise exact. | `wave3_evidence/U8/probes.json` group `shape-F-U8-1` (8/8 issued invoices); `invoicing.py` L290-297 (the `lines.append({...})` literal) | Recommend one-line fix + re-gate (orchestrator: pre- or post-merge). No tolerance/mapping change. |
| **F-U8-2** | U8 (inherited U7 F-U7-1) | medium (behavioural) | For the 3 fixture-seeded periods (tenant 1: Nov/Dec-2025, Jan-2026; ids `40000000-…` ≠ `md5(tenant‖start)`), Oracle `sp_finalize_rating` inserts `RATING_RESULTS` with `PERIOD_ID=md5(…)` → `ORA-02291 (FK_RR_PERIOD)` → `sp_issue_invoice` **raises and issues nothing**. The port appends a `results[]` element with a dangling `period_id` to the fixture period and **issues the invoice** (`period_id` = md5, not a `rating_periods._id`). | probe `F-U8-2` (tenant 1 Jan-2026): invoice exists=1, `rating_periods._id=c352effc…`: 0, fixture period `results` len 2 | U7 code path; recorded in wave 2b. Now has a business consequence — orchestrator to decide (loader-side id normalisation vs. keeping Oracle's error). Not a U8 defect. |
| **F-X-1** | U8+U9 (+U6/U7) | medium (cutover) | Three `pkg_ow_util.log_msg` call sites, two counter contracts: `rating.log_msg` (U7, used by U8) `{_id:'SEQ_BILLING_AUDIT_LOG', value, ns}` with self-reconcile; `util.log_msg` (U6, used by U9) `{_id:'seq_billing_audit_log', seq, ns}` requiring a seed. Golden `counters` seeds neither. LIVE-demonstrated `DuplicateKeyError`/silent loss when both run on one store. | `xunit/cross_unit.json` group `F-X-1` | Consolidate before cutover (one counter id, one field, one seed in `counters`). |
| F-U8-3 | U8 | info | Failed issue (no covering subscription) persists exactly one `RATING compute tenant=…` audit row (autonomous in Oracle too) and nothing else. Parity. | probes `issue` (unknown tenant, tenant 1 Dec-2025) | none |
| F-U9-1 | U9 | info | `sp_suspend_overdue` iterates candidate tenants **sorted**; Oracle's `SELECT DISTINCT` order is unspecified. Only the order of `suspended tenant=` audit rows can differ; data identical. | `dunning.py` `sorted(...)` | none |
| F-U9-2 | U9 | info | Route `/api/dunning/*` and `jobs.py` are Mongo-only (PR head "retire PostgreSQL dunning routes"); `_store()` needs `MONGODB_ATLAS_URI` at request time — cutover wiring (as noted for U6). | `routes.py` `_store()` | orchestrator scope |
| X-1 | shared | info | Fixture `INVOICES.PERIOD_ID` points at tenant 1's periods for tenants 2/5/6 — source quirk, mirrored exactly. | §2.3 | none |

## 4. Grading-only amendments (described, **not applied** — orchestrator decides)

None warranted: every Tier-1..4 comparison is exact under the frozen tolerances, and the flags above are code/shape
findings, not grading artefacts. Two notes, neither applied:

1. The recon gates (both units) grade the **loaded** clone only; the mutating procedures are graded via the 11 recorded
   transcripts' *return values*. A Tier-3 diff of the clone *after* Tier-4 (against an Oracle replay) is what would
   have caught F-U8-1 mechanically. Not a tolerance change — a possible driver enhancement for the orchestrator's
   backlog.
2. U8's driver does not reset its clone after Tier-4 (U9's does), which is why any second gate on the same load fails
   Tier-1 (run 1 here, and wave 2b for U7). Harmless for grading; a `--reset-after` in the driver would remove the
   false alarm.

## 5. Attestation

- Heads: U8 `0024b45ed39005012ca88669be4dc80565a3c994` (PR #1447), U9 `9f67ec79059fc25bd04d56d1891cd0851a9c47ee`
  (PR #1444) — fetched at 03:20Z, re-verified against `origin` and `gh pr view` headRefOid at 03:58Z (unchanged). All
  gates, loaders, unit tests and probes ran from detached worktrees at exactly these commits.
- Evidence: `wave3_evidence/U8/{gate_run1,gate}/…`, `drift_source_recount.txt`, `load_report.recon.json`,
  `probe_u8.py`, `probes.json`; `wave3_evidence/U9/{gate_run1,gate}/…`, `load_report.recon.json`, `probe_u9.py`,
  `probes.json`; `wave3_evidence/xunit/{cross_unit.py,cross_unit.json,golden_pre_fingerprint.json}`. No secret values
  appear in any evidence file (grep-verified).
- Nothing outside `replay_u8_*` / `replay_u9_*` was written by the reviewer; no legacy write; no fixture restart or
  reseed; no code, tolerance, mapping or canonicalization change; the parent checkout was not touched.
