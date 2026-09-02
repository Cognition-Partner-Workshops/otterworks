# Wave 2b — independent reconciliation report, Part 1 — re-attestation pass (U6, U7)

Run `tp-run/mongodb-20260901T205236Z` · mapping **v1.0** (run-branch `03_mapping_spec.json`, sha256 `57de55f2…7bb45`,
byte-identical at both PR heads and at run-branch head `1c03cce7`) · tolerances **v1** (`d67ccdda…4ada7`) ·
canonicalization **v1** (`527cf87c…3eb9`) · target `ow_tp_mongodb_205236` (quarantine `ow_tp_mongodb_205236_quarantine`)
· secret `MONGODB_ATLAS_URI` (name only) · fixtures: Oracle `localhost:52521/FREEPDB1` user `ow_billing`, Postgres
`localhost:5432/otterworks` schema `otterworks_demo`, LocalStack DynamoDB `localhost:4566` table
`otterworks-file-metadata` · manifest `testdata/legacy/manifests/demo.json` sha256
`0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89` (re-verified on the parent checkout) · recon
params `--seed 714559852 --param batch_no=85559852 --param source_ns=demo` · source-load cap 1.
Session: 2026-09-02 04:33 → 04:45 UTC, parent machine, separate clone `~/wave_recon/otterworks` (worktree
`~/wave_recon/w2b_part1_wt`). This session converted nothing in wave 2b and did not read the children's diagnoses
(`u6.recon.json`, `u7.recon.json`, `recon_report_u*.py`, `report.md`).

## 0. Wave-close brief (one page)

**Wave verdict: PASS (carried).** Both wave-2b units are already **merged into the run branch** and each PR branch's
*current* head is exactly the head the prior wave-2b LIVE recon re-loaded from and gated
(`tp-run/mongodb-20260901T205236Z--wave2b-recon:.migration/recon/wave_reports/wave2b.md`, commit `c2a710a2`,
2026-09-02 02:22 UTC — reproduced verbatim below as §1–§4 of the prior report). Per the wave instruction ("units whose
PR is already merged into the run branch: attest the merged head and carry the PASS from the prior wave report for that
head"), neither unit was re-graded and the LIVE gate window was not consumed; there are **no unmerged units** in this wave.

| Unit | PR | Current PR-branch head (attested) | Merge commit on run branch | Merged? | Carried verdict (source) |
|---|---|---|---|---|---|
| U6 `PKG_OW_UTIL` + `PKG_PLANS` → `ow_billing.util` / `ow_billing.plans` (+ `plans_api`), Tier-4 clone `replay_u6_*` (13 collections) | #1440 | `f463577b014d4f8fc43328ad23af9b0470f30762` | `a793f45cd83fd8ce540b9d02a1444c2dbebcc110` | yes (`merge-base --is-ancestor`) | **PASS** — prior LIVE gate @ `f463577b` after reload from head: T1 14/14 · T2 67/67 · T3 1006/1006 full diff (embeds `results` 3 + `lines` 2) · T4 5/5 (PLANS-001…005), 0 warnings; probes 71/72 (1 declared F-U6-1); run 1 on the child's pre-existing clone was *refused by preflight* (child's own Tier-4 residue, not source drift) |
| U7 `PKG_RATING` → `ow_billing.rating` (D10), Tier-4 clone `replay_u7_*` (12 collections) | #1439 | `f05741f3d9cc9acb6c24dedac6d2217351c83318` | `fbe9aec20092652022614b1b207363676457881e` | yes (`merge-base --is-ancestor`) | **PASS** — prior LIVE gate @ `f05741f3` after reload from head: T1 5/5 · T2 23/23 · T3 892/892 full diff (embed `results` 3) · T4 8/8 (RATING-001…008), 0 warnings; probes 64/64; run 1 on the child's pre-existing clone FAILed (rating_periods 3 vs 4 = child's RATING-008 residue; Oracle re-counted 3/3 twice → not drift) |

Head verification (this session, `git fetch origin --prune` at 04:34 UTC): `origin/…--u6` = `f463577b`, second parent
of `a793f45c`; `origin/…--u7` = `f05741f3`, second parent of `fbe9aec2`; both ancestors of run-branch head
`1c03cce7` (wave-2b close commit `080d6319`). **Unit-owned files unchanged** between each head and `1c03cce7`
(empty `git diff`): U6 — `services/legacy-billing/app/ow_billing/{util,plans,plans_api}.py`,
`scripts/tp_mongo/{load_replay_u6,recon_u6,recon_report_u6}.py`, `tests/test_ow_billing.py`, `.migration/recon/U6/**`,
`procs/oracle/transcripts/plans/**`; U7 — `app/ow_billing/rating.py`, `scripts/tp_mongo/load_u7.py`,
`.migration/recon_ext/recon_u7.py`, `tests/test_rating.py`, `.migration/recon/U7/**`, `procs/oracle/transcripts/rating/**`.
The one U6-touched file that *did* change after merge is `app/ow_billing/routes.py`: purely additive wave-3 (U9)
`call_entrypoint` branches for `billing.fn_overdue_accounts` / `sp_schedule_dunning` / `sp_suspend_overdue`; the U6
`plans` branches are byte-identical — graded by the wave-3 recon, not a U6 regression. Evidence:
`wave2b_part1_reattest_evidence/attested_heads.json`.

**Cheap state check (no re-grade; one serial read-only Oracle connection: 14 `COUNT(*)` + `FIXTURE_META` + 2 sequence
reads + `USER_SOURCE` reads ≈ 2 s; target reads only):** confirms the carried PASS still describes the *current*
target/fixture state after wave 3 (U8/U9) ran on the same machine (`source_counts.json`, `target_counts.json`,
`provenance_check.json`):

| Population | Source (fixture, 04:38:16Z) | Golden target | `replay_u6_*` clone | `replay_u7_*` clone | Prior LIVE report (02:22Z) |
|---|---|---|---|---|---|
| `CODES` / `codes` | 32 | 32 | 32 (values equal, fresh ObjectIds) | — (not cloned) | 32 |
| `TENANTS` / `tenants` · `PLANS` / `plans` | 69 · 3 | 69 · 3 | 69 · 3 | 69 · 3 | same |
| `SUBSCRIPTIONS` · `SUBSCRIPTIONS_HIST` | 69 · 0 | 69 · 0 | 69 · 0 | 69 · 0 | same |
| `USAGE_EVENTS` | 814 | 814 | 814 | 814 | 814 |
| `RATING_PERIODS` · `RATING_RESULTS`/Σ`results[]` | 3 · 3 | 3 · 3 | 3 · 3 | 3 · 3 | 3 · 3 |
| `INVOICES` · `INVOICE_LINES`/Σ`lines[]` | 3 · 2 | 3 · 2 | 3 · 2 | 3 · 2 | 3 · 2 |
| `CREDIT_NOTES` · `DUNNING_ATTEMPTS` · `NOTIFICATIONS` | 5 · 1 · 1 | 5 · 1 · 1 | 5 · 1 · 1 | 5 · 1 · 1 | same |
| `BILLING_AUDIT_LOG` | 1 (`log_id=1`, PLANS/fn_list_plans, 22:53:00) | 1 (`_id` 1) | 1 (`_id` 1) | 1 (`_id` 1) | 1 (the wave-0 observer row) |
| Clone canonical sha256 vs golden (11 U6 + 11 U7 collections) | — | — | **11/11 equal** | **11/11 equal** | equal after reload |
| Counters | `SEQ_BILLING_AUDIT_LOG`=2, `SEQ_SUBSCRIPTIONS_HIST`=1 | shared `counters` has **no** audit-seq doc (3 U1 docs) | `{seq_billing_audit_log: 1, seq_subscriptions_hist: 0}` | `{SEQ_BILLING_AUDIT_LOG: value 1, ns}` | same (F-X-1 still open) |
| `FIXTURE_META.INITIALIZED_AT` | `2026-09-01 20:53:10.961888` | — | — | — | same |
| `PKG_OW_UTIL` / `PKG_PLANS` / `PKG_RATING` | `USER_OBJECTS` VALID ×3; live bodies == checked-in `packages/0{1,2,3}_*.sql` (whitespace-normalized) | — | — | — | same |
| Tier-4 provenance | checked-in `db/oracle/**/*.sql` sha at `1c03cce7` = `0d326cad…` = `procs/oracle/transcripts/ORACLE_SOURCE_SHA` = every transcript's `oracle_source_sha` | | | | `0d326cad…` |
| `*__staging` residue · quarantine (as sets) | — | none · `bad_csv_list` 31, `dirty_signup_dt` 50, `invoice_feed_orphan_lines` 37, `orphan_document_snapshots` 6 (U6/U7 declare none; expected 0 == observed 0) | | | same |

All equal to the attested state: no source drift since the LIVE gate (audit-log count still 1, sequence still 2 → no
later wave invoked `PKG_*` PL/SQL against the fixture), both replay clones are exactly at the fixture baseline (the
wave-3 children's Tier-4 replays used their own `replay_u8_*`/`replay_u9_*` clones, which are present and out of
scope here), no post-attestation reload of U6/U7 is evident and none was needed → the carried PASSes stand. Unit tests
at the run head (`test_ow_billing.py` 5, `test_rating.py` 17, `test_load_replay_u6.py` 6): **28 passed**.

**Fixtures:** Oracle, Postgres, LocalStack containers healthy (up ~8 h); nothing restarted, reseeded or modified;
nothing written to the target.

**Findings (carried, unchanged; none blocking):** F-U6-1 `f_str2dt` strictness (declared, no caller); F-U6-2
`POST /plan-change` repeated → 500 (ORA-00001 parity); F-U7-1 re-finalising a fixture-seeded period whose id is not
`md5(tenant||start)` succeeds on Mongo but would raise `ORA-02291` on Oracle; F-U7-2 child narrowed `GRADED_SOURCES`
to exclude `billing_audit_log` — prior session graded it independently, equal; **F-X-1** the two `log_msg` ports still
carry incompatible `counters` contracts (`replay_u6_counters` `{_id:'seq_billing_audit_log', seq}` vs
`replay_u7_counters` `{_id:'SEQ_BILLING_AUDIT_LOG', value, ns}`), and the shared golden `counters` still has no
audit-sequence document (verified today: 3 U1 docs only) — this remains an open pre-cutover item, now also relevant
to the merged U8/U9 `log_msg` callers. No new findings.

**Grading-only amendments (described, NOT applied):** none required for the verdict. Advisory (carried from the prior
§4): record in `05_decisions.md` the single `counters` contract for `SEQ_BILLING_AUDIT_LOG` / `SEQ_SUBSCRIPTIONS_HIST`
and seed it from `USER_SEQUENCES.LAST_NUMBER` (now 2 / 1) at cutover; note that the Tier-4 source of truth for U6/U7 is
the recorded transcript tied to `ORACLE_SOURCE_SHA` (valid while live `USER_SOURCE` == checked-in SQL, which holds today).

**Cost line (this pass):** U6 — 0 gate runs, 0 reloads; U7 — 0 gate runs, 0 reloads. Shared: 1 serial Oracle pass
(14 COUNT + FIXTURE_META + 2 sequence rows + 3 `USER_SOURCE` bodies + `USER_OBJECTS`; ≈ 2 s, one connection, under the
cap of 1) + 1 short follow-up connection for the body comparison; target: 64 `count_documents`, 6 `$size` aggregates,
22 full-collection canonical fingerprints (clone vs golden), 3 small `find`s, `list_collection_names` ×2; git
fetch/merge-base/diff checks; 28 unit tests (0.2 s). Wall-clock ≈ 12 min including report writing.

---
---

# Prior LIVE report reproduced verbatim (`--wave2b-recon` @ `c2a710a2`, 2026-09-02 02:22 UTC)

# Wave 2b — independent reconciliation report (U6, U7)

Run `tp-run/mongodb-20260901T205236Z` · mapping **v1.0.1** (sha256 `57de55f2…7bb45`) · tolerances **v1**
(`d67ccdda…4ada7`) · canonicalization **v1** (`527cf87c…c3eb9`) · target `ow_tp_mongodb_205236` (quarantine
`ow_tp_mongodb_205236_quarantine`) · secrets by NAME only (`MONGODB_ATLAS_URI`, `OW_BILLING_FIXTURE_DSN`) · mode
**LIVE** on the parent machine's canonical fixtures (Oracle `localhost:52521/FREEPDB1` user `ow_billing`; manifest
sha256 `0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89`; `FIXTURE_META.INITIALIZED_AT =
2026-09-01 20:53:10.961888` before and after) · seed `714559852` · params `batch_no=85559852 source_ns=demo` ·
source-load cap 1 honoured (one Oracle connection at a time; gates, loaders and probes strictly serial).
Reviewer converted nothing in this wave and did not read the children's diagnoses (`u6.recon.json`,
`u7.recon.json`, `recon_report_u*.py`, `report.md`) before re-running. Fixtures were neither restarted nor reseeded;
the Oracle source was observed with **plain SQL only** (the `PKG_*` packages write `BILLING_AUDIT_LOG` — see wave 2a).
Checkouts were detached git worktrees under `~/wave_recon/heads/{u6,u7}` at the exact PR heads.

## 0. Wave-close brief (one page)

| Unit | PR / head attested | Load state graded | Gate (LIVE, verbatim per-unit driver) | Probes | Verdict |
|---|---|---|---|---|---|
| **U6** `PKG_OW_UTIL` + `PKG_PLANS` → `ow_billing.util` / `ow_billing.plans` (+ Flask blueprint `plans_api`), Tier-4 clone `replay_u6_*` (13 collections) | PR #1440, branch `--u6` @ **`f463577b014d4f8fc43328ad23af9b0470f30762`** (remote head re-verified after the run) | pre-existing clone gated first → driver preflight **refused** (“clone is not at the fixture baseline”: 71 subs / 2 hist / 3 audit rows = the child's own Tier-4 replay residue); **re-loaded by me from this head** (`scripts/tp_mongo/load_replay_u6.py`, 01:47:33→01:47:45Z), then gated | **PASS** T1 14/14 · T2 67/67 · T3 1006/1006 (full diff; embeds `results` 3 + `lines` 2 graded) · T4 5/5 (PLANS-001…005), 0 warnings | **71/72 ok**; the 1 flag is the child-declared `f_str2dt` leniency gap (no caller) — §3 F-U6-1 | **PASS** |
| **U7** `PKG_RATING` → `ow_billing.rating` (D10), Tier-4 clone `replay_u7_*` (12 collections) | PR #1439, branch `--u7` @ **`f05741f3d9cc9acb6c24dedac6d2217351c83318`** (remote head re-verified after the run) | pre-existing clone gated first → **FAIL** T1 `replay_u7_rating_periods` rows 3 vs docs 4, `RATING_RESULTS` 3 vs Σ`results` 4 (= the child's own RATING-008 finalize residue, not source drift: Oracle re-counted 3/3 twice); **re-loaded by me from this head** (`scripts/tp_mongo/load_u7.py`, 01:57:22→01:57:31Z), then gated | **PASS** T1 5/5 · T2 23/23 · T3 892/892 (full diff; embed `results` 3 graded) · T4 8/8 (RATING-001…008; transcripts' `ORACLE_SOURCE_SHA` = live `USER_SOURCE`), 0 warnings | **64/64 ok** (after fixing two arithmetic slips in my own script; 3 runs, clone reloaded before each) — 1 semantic edge recorded as F-U7-1 | **PASS** |
| **Cross-unit** | | | | 12/13 — the 1 flag is F-X-1 (counter contract split) | **PASS** with findings |
| **Wave 2b** | | | | | **PASS** |

- **Drift?** None on the source: `BILLING_AUDIT_LOG` = 1 row and `SEQ_BILLING_AUDIT_LOG.last_number` = 2 before,
  between and after every step (the wave-0 observer row explained in wave 2a). Both first-run failures were
  **target-side replay residue** left by the children's own Tier-4 runs on their replay clones; both loaders are
  drop-and-recreate, so reloading from the head restored the baseline and the gates went green. No re-triage
  of the source was needed beyond the two re-counts (3/3, 1/1 stable).
- **Idempotency.** U6 reloaded 4×, U7 reloaded 5× from the heads: canonical sha256 of every clone collection
  identical run-to-run (U6 `replay_u6_codes` differs only in fresh `ObjectId` `_id`s, values identical to golden).
- **Golden untouched.** All 13 golden collections + 4 quarantine classes byte-identical to the wave
  pre-fingerprint (`golden_pre_fingerprint.json`) after every gate/probe; quarantine compared as **sets**:
  `bad_csv_list` 31 · `dirty_signup_dt` 50 · `invoice_feed_orphan_lines` 37 · `orphan_document_snapshots` 6
  (U6/U7 declare no quarantine targets; expected 0 new, observed 0 new).
- **App-level replay (plain SQL vs Python on the clone, all equal):** U6 `fn_entitlement` 69 tenants × 6 dates =
  414 ops, `fn_list_plans` full-row, `f_md5_uuid`/`f_code_desc`/`f_dt2str` value-for-value, `sp_change_plan`
  8 semantic paths (§2.1); U7 `fn_usage_rating` 69 tenants × 8 windows = **552 ops** on all 7 numeric outputs
  (69 no-covering-sub, 2 suspension-factor, 204 non-zero overage), `fn_usage_summary` 70 × 4 = 306 grouped rows,
  `sp_finalize_rating` 5 paths, 6 read transcripts re-replayed (§2.2).
- **Findings (none blocking):** F-U6-1 `f_str2dt` strictness (declared, no caller); F-U6-2 `POST /plan-change`
  repeated → 500 (ORA-00001 parity, recorded); F-U7-1 re-finalising a *fixture-seeded* period whose id is not
  `md5(tenant||start)` succeeds on Mongo but would raise `ORA-02291` on Oracle (§3); F-U7-2 child narrowed
  `GRADED_SOURCES` to exclude `billing_audit_log` after its run-1 failure — I graded it independently: **equal**
  (1/1, all columns); F-X-1 U6 and U7 ship two `pkg_ow_util.log_msg` ports with **incompatible `counters`
  contracts** (`{_id:'seq_billing_audit_log', seq}` vs `{_id:'SEQ_BILLING_AUDIT_LOG', value, ns}`), neither
  matching the golden `counters` shape, and the shared `counters` has no audit-sequence doc at all (§3).
- **Grading-only amendments: none warranted.** (Two optional notes for the orchestrator in §4, neither applied.)
- **Cost (serial, parent machine):** **U6** — gate run 1 1.2 s (preflight refusal, 0 source statements) · reload
  11.5 s · authoritative gate ≈ 30 s (14 COUNT + 67 aggregates + full keyed fetch of 13 tables; 5 transcript
  replays) · unit tests 0.11 s (5 passed) · probes 48.3 s (≈ 520 small SQL statements on one connection; 414 +
  ~40 replay ops) · 2 extra reloads 23 s. ≈ 115 s source time. **U7** — gate run 1 1.5 s · reload 9.4 s ·
  authoritative gate 10 s (5 COUNT + 23 aggregates + full keyed fetch of 4 tables; 8 transcript replays) ·
  unit tests 0.12 s (17 passed) · probes 264.6 s × 3 runs (≈ 900 SQL statements per run: 552 rating + 280
  summary + ~70 metadata; the per-op Oracle round trip dominates) · 3 extra reloads 28 s. ≈ 14 min source
  time. Cross-unit 6 s. Total wall clock ≈ 45 min under the cap of 1.
- **Recommendation:** merge PR #1440 at `f463577b` and PR #1439 at `f05741f3` into the run branch; before U8/U9
  consolidate the `counters` contract (F-X-1) and decide whether F-U7-1's Oracle error is behaviour to keep.

---

## 1. Gate invocations (verbatim per-unit drivers; harness `mongo-migration-plugin-6d021e15/0.2.1`, `recon selftest` PASS)

The harness CLI's `recon run` covers Tiers 1–3 only; both units ship a committed driver that hands the Tier-4
callbacks to the harness's own `run_recon` (engine, tiers, tolerances, report unchanged). I ran those drivers
exactly as committed, on the exact heads, in LIVE mode:

```
# U6  (worktree ~/wave_recon/heads/u6 @ f463577b…)
python scripts/tp_mongo/recon_u6.py                # fixed args inside: unit U6, mode live, mapping v1.0.1,
                                                   # tolerances v1, canonicalization v1, seed 714559852,
                                                   # batch_no=85559852 source_ns=demo, secrets by name
# U7  (worktree ~/wave_recon/heads/u7 @ f05741f3…)
python .migration/recon_ext/recon_u7.py --unit U7 --mapping .migration/03_mapping_spec.json \
  --tolerances .migration/02_tolerances.json --canonicalization .migration/canonicalization.json \
  --mode live --source-dsn-secret OW_BILLING_FIXTURE_DSN --target-uri-secret MONGODB_ATLAS_URI \
  --target-db ow_tp_mongodb_205236 --seed 714559852 --param batch_no=85559852 --param source_ns=demo --out <dir>
```

| Unit | Run | Load state | Result | Detail |
|---|---|---|---|---|
| U6 | 1 | child's clone as found (subs 71, hist 2, audit 3, counters seq 18/5) | **refused** by driver preflight | `RuntimeError: replay_u6_* clone is not at the fixture baseline; re-run load_replay_u6.py before recon` — the child's own Tier-4 `sp_change_plan` replays (PLANS-004/005) had mutated the clone. Not a source drift (Oracle unchanged). |
| U6 | 2 | reloaded from head (69/0/814/3/3/5/1/1/1 + codes 32, tenants 69, plans 3, counters 2) | **PASS** | T1 14/14 · T2 67/67 · T3 1006/1006 (full diff, `results` 3 + `lines` 2 embedded graded) · T4 5/5; `tier4_replay.json` source==target for PLANS-001…005 |
| U7 | 1 | child's clone as found (rating_periods 4, audit 9, counter 9) | **FAIL** | T1 `replay_u7_rating_periods root_count rows=3 vs docs=4`, `embed_cardinality rows(RATING_RESULTS)=3 vs sum(len(results))=4` — the child's RATING-008 finalize residue. Oracle `RATING_PERIODS`/`RATING_RESULTS` re-counted twice: 3/3, 3/3 → **not source drift**. |
| U7 | 2 | reloaded from head (69/0/814/3/3/5/1/1/1 + plans 3, tenants 69, counters 1) | **PASS** | T1 5/5 · T2 23/23 · T3 892/892 (full diff, `results` 3 embedded graded) · T4 8/8; `tier4_provenance.json`: transcripts' `oracle_source_sha 0d326cad…` == current, and I verified live `USER_SOURCE` == checked-in `03_pkg_rating.sql` so the file-based sha is live-valid |

Unit tests on the heads: U6 `services/legacy-billing/tests/test_ow_billing.py` 5 passed; U7
`services/legacy-billing/tests/test_rating.py` 17 passed.

Tier-4 design note (both units, accepted): the *source* side of Tier 4 is the recorded Oracle transcript
(`procs/oracle/transcripts/{plans,rating}/*.json`), not a live PL/SQL call — correct, because calling the
packages would write `BILLING_AUDIT_LOG`. Provenance is tied to `ORACLE_SOURCE_SHA` and I independently
confirmed live `USER_SOURCE` bodies of `PKG_OW_UTIL`, `PKG_PLANS`, `PKG_RATING` equal the checked-in files.

## 2. Adversarial probes (scripts and JSON evidence under `~/wave_recon/w2b/{U6,U7}/probe_u*.py`, `probes.json`, `cross_unit.py`)

### 2.1 U6 — 71/72 ok (`probe_u6.py`, 48.3 s, clone reloaded before and after)

- **Clone baseline vs golden:** 11 collections canonical-sha-equal to golden; `codes` equal ignoring ObjectId;
  index specs equal (keys/unique/TTL); `usage_events` validator cloned strict/error; no `*__staging` residue.
- **Counters:** `replay_u6_counters` seeded `seq_billing_audit_log=1`, `seq_subscriptions_hist=0` ==
  `USER_SEQUENCES.last_number-1` (both NOCACHE so exact) == max(`log_id`) in the cloned audit log; BSON long.
- **`PKG_OW_UTIL` parity (plain SQL):** `f_md5_uuid` == `STANDARD_HASH(…,'MD5')` on 7 inputs incl. empty and
  UTF-8; `f_code_desc` == `CODES` for all 32 codes plus the `NO_DATA_FOUND → UNKNOWN(val)` / NULL → `UNKNOWN(-1)`
  branches; `f_dt2str` == `TO_CHAR(DD-MON-YY)`. **`f_str2dt` ≠ `TO_DATE('DD-MON-YY')` on 5/15 strings**
  (`01-JAN-2026`, `01-JANUARY-26`, `01 JAN 26`, `01/JAN/26`, `01-JAN-6` — Oracle is lenient, the port's regex
  strict → returns NULL). `USER_SOURCE` shows no caller of `f_str2dt` outside `PKG_OW_UTIL` → F-U6-1.
- **`fn_list_plans`:** full 6-column row parity incl. `ORDER BY monthly_fee, code` (a first "mismatch" was my
  own query aliasing `monthly_fee` to a string — fixed, rerun equal); writes exactly one audit row
  (`PLANS`/`fn_list_plans`, long `log_id`, `ns`); with all plans inactivated → `[]` (audit row still written);
  `NVL(active_yn,'N')='Y'` excludes NULL (data has only `'Y'` — branch untested by data, recorded).
- **`fn_entitlement`:** 69 tenants × 6 dates = 414 ops equal on all 7 fields (345 hits, 69 no-entitlement);
  unknown tenant → none; read-only (no audit row, like the PL/SQL); source has no `starts_on` ties per tenant
  so `ORDER BY starts_on DESC / ROWNUM<=1` is deterministic.
- **`sp_change_plan` (8 paths):** new id == `f_md5_uuid(tenant||plan||YYYY-MM-DD)`; row shape == columns with
  explicit nulls; prior open row closed `ends_on = eff-1`, `status DECODE(10→10)`; `TRG_SUBSCRIPTIONS_HIST`
  image == `:OLD` row, `hist_op UPD`, `hist_id` from counter, `hist_dt 'DD-MON-YY HH24:MI:SS'`; entitlement
  boundary 02-28 → old plan (inclusive `ends_on`), 03-01 → new; same change twice → `DuplicateKeyError`
  (ORA-00001 parity) with transaction rolled back yet audit row written (autonomous-txn parity); closed rows
  untouched; open **suspended (20)** row closed with `DECODE(20→10)` and `suspended_on` preserved; open
  **cancelled (30)** row stays 30 (`TRG_SUB_NO_UNCANCEL`); history keeps the *prior* status; `hist_id` strictly
  sequential; `eff == starts_on` of the open row leaves it open (faithful to the PL/SQL quirk); FK miss on
  tenant/plan → `LookupError`, nothing written, audit row written; tenant with no open sub → insert only.
- **Audit log:** `_id==log_id` long, `module<=30`, `message<=4000`, `logged_at` ms-truncated naive, `ns`;
  message text equals the PL/SQL concatenation; ids strictly sequential from the seeded counter.
- **HTTP (Flask test client on the blueprint):** `GET /api/plans` == PLANS-001; `GET entitlement` tenant 2 ==
  PLANS-003 (`GROWTH/growth/500/suspended`); unknown tenant 404; bad plan / bad date 400; `POST plan-change`
  200 with `latest_plan/latest_start` + rows; **repeat POST → 500** (F-U6-2); legacy `app.py` imports the
  blueprint with no URL-rule collisions (19 rules, 3 new).
- **Golden / quarantine / source:** unchanged.

### 2.2 U7 — 64/64 ok (`probe_u7.py`, 264.6 s, clone reloaded before each of 3 runs and after)

- **Clone baseline vs golden:** all 11 source collections canonical-sha-equal; index specs equal (incl. the
  unique `tenant_id_1_period_start_1` on `rating_periods` = `UQ_RATING_PERIODS`); validators equal; no
  staging residue; counter `{_id:'SEQ_BILLING_AUDIT_LOG', value:1(long), ns}` == `last_number-1` == max `log_id`.
- **What the U7 gate leaves ungraded, graded here:** `replay_u7_billing_audit_log` == `BILLING_AUDIT_LOG`
  keyed on all columns (1/1); `rating_periods.results[]` == `RATING_RESULTS` row-for-row on 9 columns (3/3);
  `results[]` length distribution {1:3} == child rows per period; element types `Int64`/`Decimal128`/date.
- **Null / duplicate / boundary / distribution:** NULL counts per field equal for `usage_events`
  (0/0/0), `subscriptions` (`ends_on` 69, `suspended_on` 68), `rating_periods`, `plans`; no duplicate business
  ids and `_id==id` everywhere; `(tenant_id, period_start)` unique; `usage_events` min/max `occurred_at`
  (2026-02-01 10:00 … 2026-02-28 10:00), min/max/sum units (1 / 2201 / 336 293), 69 distinct tenants equal;
  `kind_cd` distribution {1:504, 2:149, 3:161} equal (no `UNKNOWN` in data — recorded).
- **`fn_usage_rating` parity — 552 ops:** the PL/SQL arithmetic re-expressed as one Oracle SQL statement
  (`NVL/LEAST/GREATEST/ROUND/ADD_MONTHS`, `TO_CHAR(...,'YYYYMMDD')` string window, date-subtraction factor) vs
  the Python on the clone: **0 mismatches** over 69 tenants × 8 windows (Jan/Feb/Mar/Dec, straddling Feb-15→Mar-15,
  single-day Feb-1 and Feb-28, Jan-15→Feb-14); exercised 69 no-covering-subscription cases (NULL quota/overage
  propagation), 2 suspension-factor cases (tenant 2, status 20), 204 non-zero overages, the double rollover cap
  (tenant 1 Feb: prior 300 → 200 = 2×included) and the `ADD_MONTHS(-3)` window (Mar sees Dec+Jan, not Nov);
  `add_months` == Oracle incl. the last-day-of-month rule on 5 dates; unknown tenant → `used 0, quota NULL,
  rollover 0, billable 0, overage NULL` on both; day-string boundary: a window ending on the event day counts
  the 10:00 events, the previous day does not (both stacks); tz-aware inputs rate like dates; each compute writes
  exactly one `RATING`/`compute tenant=… used=… billable=…` audit row (553 = 1 + 552).
- **`fn_usage_summary` parity:** 70 tenants × 4 windows, 306 grouped rows equal (kind order, count, units);
  writes no audit row (as the PL/SQL).
- **`sp_finalize_rating` (5 paths, clone only):** new period `_id/id == f_md5_uuid(tenant||YYYY-MM-DD)` and
  `results[0].id == f_md5_uuid(period_id)` (checked against `STANDARD_HASH`); doc shape == `RATING_PERIODS`
  columns + `ns`; `results[0]` == `RATING_RESULTS` columns with `subscription_id` from the covering sub,
  `rollover_units = GREATEST(quota-used,0)`, `created_at = period_end`; types `Int64`/`Decimal128`; two audit rows
  (compute + `finalized period=<id>`); re-finalize same (tenant, start) with a new `period_end` → UPDATE path:
  `period_end` updated, still 1 element, same ids, only the 4 amounts refreshed (`quota_units`, `subscription_id`,
  `created_at` keep INSERT-time values, as in PL/SQL); no covering subscription → `RatingIntegrityError`
  (ORA-01400 parity), nothing written, compute audit row present but no `finalized` row; audit ids strictly
  sequential and counter == max; deleting the counter doc → `_reconcile_log_sequence` resumes at max+1.
  Re-finalising a **fixture-seeded** period (tenant 1, Jan-2026, id `4000…02`) appends a second `results[]`
  element under the md5 id → see F-U7-1.
- **Transcripts:** the 6 read-only rating transcripts re-replayed on the (dirty) clone equal the recorded
  Oracle `business_fields`; the 2 finalize transcripts were graded by the gate on the fresh clone (8/8).
- **Golden / quarantine / source:** unchanged.

### 2.3 Cross-unit — 12/13 ok (`cross_unit.py`)

- Shared references hold in golden and in both clones: `subscriptions.plan_id ⊂ plans`,
  `subscriptions/usage_events/rating_periods.tenant_id ⊂ tenants`, `results[].subscription_id ⊂ subscriptions`.
- `replay_u6_*` and `replay_u7_*` are value-identical at baseline on the five shared collections.
- `codes` == `CODES` for `PLAN_TIER`/`SUB_STATUS`/`USAGE_KIND`; U7 `KIND_DECODE` and U6's tier `DECODE` equal the
  `CODES` descriptions; every status/kind/tier value present in data has a `CODES` row (no live `UNKNOWN(...)`).
- **F-X-1** (the flag): the two `log_msg` ports disagree on the `counters` document contract — golden
  `{_id:'seq_customer_master', seq, source_sequence, ns}`; U6 `{_id:'seq_billing_audit_log', seq}` (raises
  `LookupError` if unseeded); U7 `{_id:'SEQ_BILLING_AUDIT_LOG', value, ns}` (self-seeds from max `log_id`,
  swallows `PyMongoError`). The shared golden `counters` has **no** audit-sequence doc under either key.
- Golden + quarantine byte-identical to the pre-fingerprint; Oracle identity unchanged.

## 3. Findings (none blocking; none require a tolerance or canonicalization change)

| ID | Unit | Severity | Finding | Evidence |
|---|---|---|---|---|
| F-U6-1 | U6 | low (declared) | `util.f_str2dt` is stricter than `TO_DATE(x,'DD-MON-YY')` (4-digit years, full month names, `/` or space separators, 1-digit day/year are NULL in the port, valid in Oracle). No PL/SQL caller outside `PKG_OW_UTIL`; U1's D3 dirty-date handling is separate. | `probe_u6.py` util probe, 5/15 strings; `USER_SOURCE` caller scan empty |
| F-U6-2 | U6 | info | `POST /api/tenants/<id>/plan-change` repeated with the same effective date propagates `DuplicateKeyError` as HTTP 500 (the legacy app would also surface ORA-00001 as 500). Transaction correctly rolled back; audit row written. | http probe, status 500 |
| F-U7-1 | U7 | **medium (edge, not in transcripts)** | `sp_finalize_rating` on a period whose stored id ≠ `md5(tenant||period_start)` (true for the three fixture-seeded periods `4000…01/02/03` of tenant 1; always false for periods the procedure itself created): Oracle's INSERT hits `UQ_RATING_PERIODS` → UPDATE by (tenant,start), then the `RATING_RESULTS` INSERT with `period_id = md5-id` fails **`ORA-02291` on `FK_RR_PERIOD`** (only `DUP_VAL_ON_INDEX` is caught) — the legacy call errors. The port instead appends a second `results[]` element whose `period_id` (md5) ≠ the parent `_id` and returns success. Behavioural divergence only for legacy-seeded periods; the RATING-008 transcript finalises a *new* period so the gate cannot see it. | `probe_u7.py` finalize probe on tenant 1 / 2026-01-01: 2 elements `{'5000…02', 'c352effc…'}`; constraints `FK_RR_PERIOD` ENABLED/VALIDATED; fixture ids `4000…03/01/02` vs `STANDARD_HASH` md5 ids `0f4dd4fc…/a0173203…/c352effc…` (plain-SQL check) |
| F-U7-2 | U7 | process | After its run-1 T1 failure the child removed `billing_audit_log` from `GRADED_SOURCES` ("write-only sink") rather than reloading; the collection is therefore ungraded by the U7 gate T1–T3. Independently graded here: equal (1/1, all columns). | `recon_u7.py` `GRADED_SOURCES`; probe "ungraded" |
| F-U7-3 | U7 | info | `rating.py` re-implements `pkg_ow_util.f_md5_uuid` and `log_msg` (`md5_uuid`, `log_msg`, `_next_log_id`) instead of using U6's `ow_billing.util` — unavoidable while the branches are parallel, but the two copies must converge at merge (see F-X-1). | `rating.py` L100–198 vs `util.py` L82–103 |
| F-X-1 | U6+U7 | **medium (integration)** | Incompatible `counters` contracts for the same Oracle sequence `SEQ_BILLING_AUDIT_LOG` (key case, field `seq` vs `value`, presence of `ns`/`source_sequence`), and no seed for it in the shared `counters` (U1's target; U5 declared it out of scope). Once both write paths point at the shared set they would run two independent sequences → colliding `log_id`s (U6 would raise `DuplicateKeyError` inside its plan-change transaction; U7 swallows and reconciles). Needs one seed (from the live sequence, now 2) and one contract before U8/U9. | `cross_unit.py` FINDING probe; `util.py` L82–91; `rating.py` L151–173 |

## 4. Grading-only amendments (described, **not applied** — orchestrator decides)

None are needed for either verdict. Two optional notes:

1. *Optional:* the U7 unit mapping could re-include `billing_audit_log` in `GRADED_SOURCES` now that the target
   holds the observer row — it passes (1/1). Purely additive coverage; no shape/rule/tolerance change.
2. *Optional:* the mapping spec could declare the `counters` document contract (`_id` casing, `seq` field,
   `ns`, `source_sequence`) so U6/U7/U8/U9 converge on it (F-X-1). This is a spec clarification, not a
   tolerance change.

## 5. Attestation

| Unit | PR | Head SHA the LIVE gate + probes ran against | Remote head at report time |
|---|---|---|---|
| U6 | #1440 `tp-run/mongodb-20260901T205236Z--u6` | `f463577b014d4f8fc43328ad23af9b0470f30762` | same |
| U7 | #1439 `tp-run/mongodb-20260901T205236Z--u7` | `f05741f3d9cc9acb6c24dedac6d2217351c83318` | same |

Run branch base `551dbe44e38c62247a3208d9956979cccc08f779`. Both replay clones were **reloaded to the fixture
baseline** at the end (02:18Z) and left in place; golden collections, quarantine DB and the Oracle/Postgres/
DynamoDB fixtures were not modified. Evidence bundle (not committed, machine-local): `~/wave_recon/w2b/`
(`pre_state.json`, `golden_pre_fingerprint.json`, `U6/{gate,gate_run1.log,gate.log,load_report.*.json,
probe_u6.py,probe_u6.log,probes.json}`, `U7/{gate,gate_run1,gate_run1.log,gate.log,load_report.*.json,
probe_u7.py,probe_u7.log,probes.json}`, `cross_unit.{py,json,log}`).
