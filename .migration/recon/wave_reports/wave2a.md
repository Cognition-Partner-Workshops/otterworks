# Wave 2a — independent reconciliation report, Part 1 — re-attestation pass (U5)

Run `tp-run/mongodb-20260901T205236Z` · mapping **v1.0** (run-branch `03_mapping_spec.json`, sha256 `57de55f2…`,
byte-identical at PR head and run-branch head) · tolerances **v1** (`d67ccdda…`) · canonicalization **v1**
(`527cf87c…`) · target `ow_tp_mongodb_205236` (quarantine `ow_tp_mongodb_205236_quarantine`) · secret
`MONGODB_ATLAS_URI` (name only) · fixtures: Oracle `localhost:52521/FREEPDB1` user `ow_billing`, Postgres
`localhost:5432/otterworks` schema `otterworks_demo`, LocalStack DynamoDB `localhost:4566` table
`otterworks-file-metadata` · manifest `testdata/legacy/manifests/demo.json` sha256
`0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89` (re-verified on the parent checkout) ·
recon params `--seed 714559852 --param batch_no=85559852 --param source_ns=demo` · source-load cap 1.
Session: 2026-09-02 04:28 → 04:36 UTC, parent machine, separate clone `~/wave_recon/otterworks`.
This session converted nothing in wave 2a and did not read the child's diagnoses.

## 0. Wave-close brief (one page)

**Wave verdict: PASS (carried).** The only wave-2a unit, **U5 (PR #1438)**, is already **merged into the run
branch** (merge commit `944c9dcb` "Merge PR #1438 (U5 billing core @ 1aefd226)"), and the PR branch's *current*
head `1aefd226d917ec0ddd604159ce7196b924050f7e` is exactly the head that the prior wave-2a LIVE recon re-loaded
from and gated (`tp-run/mongodb-20260901T205236Z--wave2a-recon:.migration/recon/wave_reports/wave2a.md`,
commit `bd880b14`, 2026-09-02 00:57 UTC — reproduced verbatim below as §1–§6 of the prior report). Per the
wave instruction ("units whose PR is already merged into the run branch: attest the merged head and carry the
PASS from the prior wave report for that head"), U5 was **not re-graded** and the LIVE gate window was not
consumed; there are **no unmerged units** in this wave.

| Unit | PR | Current PR-branch head (attested) | Merge commit on run branch | Merged? | Carried verdict (source) |
|---|---|---|---|---|---|
| U5 billing core — `subscriptions`, `subscriptions_history`, `usage_events`, `rating_periods`(+`results[]`), `billing_invoices`(+`lines[]`), `credit_notes`, `dunning_attempts`, `notifications`, `billing_audit_log` | #1438 | `1aefd226d917ec0ddd604159ce7196b924050f7e` | `944c9dcb21944c737a95cd1f3e8517d44f169ad4` | yes (`merge-base --is-ancestor`) | **PASS (DRIFT-EXPLAINED, resolved)** — prior LIVE gate @ `1aefd226` after reload from head: T1 11/11 · T2 53/53 · T3 902/902 full diff, embeds `results` 3 + `lines` 2, 0 warnings; probes 142/142; run 1 on the child's pre-existing load FAILed on `billing_audit_log` 1 vs 0 and was triaged as observer-induced source drift, not a defect (§1 below) |

Head verification (this session, `git fetch origin` at 04:30 UTC): `origin/…--u5` = `1aefd226`; it is the
second parent of `944c9dcb` and an ancestor of run-branch head `1c03cce7`. `scripts/tp_mongo/load_u5.py` and
`.migration/recon/U5/**` are unchanged between `1aefd226` and `1c03cce7` (empty diff). Evidence:
`wave2a_part1_reattest_evidence/attested_heads.json`.

**Cheap state check (no re-grade; one serial Oracle connection, 11 `COUNT(*)` + `FIXTURE_META` + 2 sequence
reads ≈1 s; target reads only):** to confirm the carried PASS still describes the *current* target/fixture
state after waves 2b and 3 ran on the same machine (`source_counts.json`, `target_counts.json`):

| Population | Source (fixture, 04:32:59Z) | Target (Mongo) | Prior LIVE report (00:48Z) |
|---|---|---|---|
| `SUBSCRIPTIONS` / `subscriptions` | 69 | 69 | 69 |
| `SUBSCRIPTIONS_HIST` / `subscriptions_history` | 0 | 0 (collection exists) | 0 |
| `USAGE_EVENTS` / `usage_events` | 814 | 814 | 814 |
| `RATING_PERIODS` / `rating_periods` · `RATING_RESULTS` / Σ`results[]` | 3 · 3 | 3 · 3 | 3 · 3 |
| `INVOICES` / `billing_invoices` · `INVOICE_LINES` / Σ`lines[]` | 3 · 2 | 3 · 2 | 3 · 2 |
| `CREDIT_NOTES` / `credit_notes` | 5 | 5 | 5 |
| `DUNNING_ATTEMPTS` / `dunning_attempts` | 1 | 1 | 1 |
| `NOTIFICATIONS` / `notifications` | 1 | 1 | 1 |
| `BILLING_AUDIT_LOG` / `billing_audit_log` | 1 (`log_id=1`, PLANS/fn_list_plans, 22:53:00) | 1 (`_id` 1) | 1 (the explained drift row) |
| `FIXTURE_META.INITIALIZED_AT` | `2026-09-01 20:53:10.961888` | — | same |
| `SEQ_BILLING_AUDIT_LOG` / `SEQ_SUBSCRIPTIONS_HIST` | 2 / 1 | — | 2 / 1 |
| `*__staging` residue · U5 collections in quarantine DB | — | none · none (expected 0 == observed 0) | none · none |
| Shared refs `codes` / `tenants` / `plans` | — | 32 / 69 / 3 | 32 / 69 / 3 |
| Quarantine DB (other units, unchanged) | — | `dirty_signup_dt` 50, `bad_csv_list` 31, `orphan_document_snapshots` 6, `invoice_feed_orphan_lines` 37 | same |

All equal to the attested state: no drift since the LIVE gate (the audit-log row count is still exactly 1 and
the sequence still 2, so no later wave's probes invoked `PKG_*` PL/SQL against the fixture), no evidence of a
post-attestation reload → the carried PASS stands.

**Fixtures:** all three containers healthy (up ~8 h); nothing restarted, reseeded or modified; nothing written
to the target.

**Findings (carried, unchanged; none blocking):** (A) `usage_events` validator `minimum: 1` (matches trigger
`units > 0`, spec text says `>= 0`) and `bsonType: long` (U6/U7 write paths must use `Int64`); `kind_cd ∈ CODES
USAGE_KIND` half of the trigger is data-true but not in the validator. (B) `counters` seeds for
`SEQ_SUBSCRIPTIONS_HIST` / `SEQ_BILLING_AUDIT_LOG` not written by U5 — must be seeded from the live sequence
(now 1 / 2), not from 1. No new findings.

**Grading-only amendments (described, NOT applied):** none required for the verdict; the prior §6 advisory notes
stand (record in `05_decisions.md` that reviewer probes must not call `PKG_*` PL/SQL on the live fixture; the
live baseline for `BILLING_AUDIT_LOG` is 1 row; align the #35 mapping note to `units > 0`; seed the two
counters from `USER_SEQUENCES.LAST_NUMBER`).

**Cost line (this pass):** U5 — 0 gate runs, 0 reloads; 1 serial source pass (11 COUNT + 2 small reads, ≈1 s
under the cap of 1); target: 9 `count_documents` + 2 `$size` aggregates + `list_collection_names` ×2;
git fetch/merge-base checks. Wall-clock ≈8 min including report writing.

---
---

# Prior LIVE report reproduced verbatim (`--wave2a-recon` @ `bd880b14`, 2026-09-02 00:57 UTC)

# Wave 2a — independent reconciliation report (U5)

Run `tp-run/mongodb-20260901T205236Z` · mapping **v1.0.1** (run-branch grading amendment on top of v1.0; U5
collections unchanged between the two) · tolerances **v1** · canonicalization **v1** · target `ow_tp_mongodb_205236`
(quarantine `ow_tp_mongodb_205236_quarantine`) · secrets by NAME only (`MONGODB_ATLAS_URI`, `OW_BILLING_FIXTURE_DSN`)
· mode **LIVE** on the parent machine's canonical fixtures (Oracle `localhost:52521/FREEPDB1` user `ow_billing`;
manifest `testdata/legacy/manifests/demo.json` sha256 `0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89`
re-verified; `FIXTURE_META.INITIALIZED_AT = 2026-09-01 20:53:10.961888` before and after) · seed `714559852` · params
`batch_no=85559852 source_ns=demo` · source-load cap 1 honoured (one Oracle connection at a time; gate, loader and
probes strictly serial). Reviewer converted nothing in this wave and did not read the child's diagnoses
(`u5.recon.json`, `recon_report_u5.py`) before re-running. Fixtures were neither restarted nor reseeded.

## 0. Wave-close brief (one page)

| Unit | PR / head attested | Load state graded | Gate (LIVE, verbatim) | Probes | Verdict |
|---|---|---|---|---|---|
| **U5** billing core — `subscriptions`, `subscriptions_history`, `usage_events`, `rating_periods`(+`results[]`), `billing_invoices`(+`lines[]`), `credit_notes`, `dunning_attempts`, `notifications`, `billing_audit_log` (Oracle `SUBSCRIPTIONS`…`BILLING_AUDIT_LOG`, 11 tables) | PR #1438, branch `--u5` @ **`1aefd226d917ec0ddd604159ce7196b924050f7e`** (not merged into the run branch) | **re-loaded by me from this head** (`scripts/tp_mongo/load_u5.py`, 00:47:37→00:47:47 UTC; 69/0/814/3/3/5/1/1/**1** inserted, staging-swap) after first gating the pre-existing load | run 1 (pre-existing load) **FAIL** — Tier-1 `billing_audit_log` rows=1 vs docs=0 → triaged as **source drift caused by an observer, not a defect** (§1); run 2 (after reload from head) **PASS** T1 11/11 · T2 53/53 · T3 902/902 (full diff, embeds `results` 3 + `lines` 2 graded, 0 findings, 0 warnings, no UNGRADED) | **142/142 ok**, 0 flags | **PASS** (drift explained, resolved by the reload) |
| **Wave 2a** | | | | | **PASS** |

- **Drift, explained.** `BILLING_AUDIT_LOG` had 0 rows at census and in the child's fixture; on the parent
  machine it has **1 row** (`log_id=1, PLANS / fn_list_plans, logged_at 2026-09-01 22:53:00`, `ORA_ROWSCN` →
  22:52:58Z). That is two hours after the seed (20:53Z) and is the audit side-effect of `PKG_OW_UTIL` being
  invoked through `PKG_PLANS.fn_list_plans` — i.e. the wave-0 recon's PL/SQL replay probes wrote it. It is not
  seed data, not a U5 loader defect (the loader has `root_where: null` and copies whatever is there), and the
  child's committed load (00:35:36Z) simply ran against a fixture that never had the row. Source re-counted
  twice (`drift_source_recount.json`): stable at 1. After reloading from the head the row is present in the
  target and the gate is green; Tier-3 checks are 902 vs the child's 901 for exactly that row. I did **not**
  touch the source. Lesson recorded for later waves: replay PL/SQL as plain SQL (as I did here) — the packages
  write `BILLING_AUDIT_LOG`, so calling them mutates the fixture.
- **Idempotency evidence.** The head reload reproduced the other eight collections **byte-identically** (sha256
  of the sorted canonical extended-JSON dump equal before/after, `pre_/post_reload_fingerprint.json`); only
  `billing_audit_log` changed (0→1). No `*__staging` residue; other units' collections untouched (codes 32 /
  tenants 69 / plans 3 / customers 25,000 / invoices 18,750 / documents 2,000 / document_snapshots 384 / files 10,000).
- **Data fidelity.** Independent full value diff from Oracle `TO_CHAR` text (no float path): 0 diffs on 897 root
  docs × all fields and on all 5 embedded elements; every declared BSON type holds exactly (`long` via `Int64`,
  `Decimal128` for all NUMBER(12,2), `int` for NUMBER(4,0)/(6,0), dates ms-truncated); NULLs are explicit BSON
  null (D2) — `subscriptions.ends_on` 69/69, `suspended_on` 68/68 — with 0 missing keys; no empty strings; no
  duplicate keys; `_id`==natural id bijection on all 9 collections; embed lengths per parent equal (`results`
  1/1/1, `lines` 2/0/0); sums/min/max exact for every money and units column; boundary docs equal.
- **Validator / indexes / TTL.** `usage_events` `$jsonSchema` (strict/error) rejects `units=0`, `units=-1`, wrong
  `ns` and int32 `units`; nothing persisted (count 814 unchanged). All declared indexes present with the right
  keys/`unique`/`expireAfterSeconds=7776000`, nothing extra. `subscriptions_history` exists empty with `_id_` only.
- **Cross-unit.** `tenant_id` sets equal to source and resolve 100 % to `tenants` on all 7 tenant-bearing
  collections; `plan_id` ⊂ `plans` (3/3); `status_cd`/`kind_cd` ⊂ the matching `codes` types (`SUB_STATUS`,
  `INV_STATUS`, `DUN_STATUS`, `NOTIF_KIND`, `USAGE_KIND`); `period_id` ⊂ `rating_periods`; `invoice_id` ⊂
  `billing_invoices`; `results[].subscription_id` ⊂ `subscriptions`; child `period_id`/`invoice_id` == parent `_id`.
- **App-level replay (plain SQL vs Mongo, 386 ops, all equal).** `PKG_RATING.fn_usage_summary` ×160,
  `PKG_PLANS.fn_entitlement` ×207, `PKG_DUNNING.fn_overdue_accounts` ×4, `fn_invoice_lines` ×3, rating rollover
  window ×9, credit-note application order, `sp_schedule_dunning`/`sp_suspend_overdue` read halves.
- **Findings (none blocking):** (A) validator is stricter than the spec text in two ways that are *correct*
  (`minimum: 1` matches the trigger's `units > 0`, not the spec's "units >= 0"; `bsonType: long` means U6/U7 write
  paths must use `Int64`); the trigger's second branch (`kind_cd ∈ CODES USAGE_KIND`) is not in the validator —
  declared by the child, data holds 3/3. (B) `counters` seeds for `SEQ_SUBSCRIPTIONS_HIST`/`SEQ_BILLING_AUDIT_LOG`
  are not written (declared; `counters` is U1's target) — note that `SEQ_BILLING_AUDIT_LOG` is now at **2** on the
  source and `log_id=1` exists in the target, so whoever seeds the counter must seed from the live sequence, not 1.
- **Grading-only amendments: none warranted.**
- **Cost (U5, serial, parent machine):** gate run 1 1.9 s · reload 9.7 s (11 SELECTs, 9 staging swaps) · gate run 2
  12.0 s (11 COUNT + 53 aggregate + full keyed fetch of 11 tables) · probes 44.7 s (≈700 small SQL statements on one
  connection; 386 replay ops) · drift recounts ~2 s · unit tests 0.1 s. ≈70 s source time total under the cap of 1.
- **Recommendation:** merge PR #1438 at `1aefd226` into the run branch; record this head as the attested SHA.
  The target now holds the state produced by the head loader against the live fixture (incl. the 1 audit row).

---

## 1. Gate invocation (verbatim harness, plugin `mongo-migration-plugin-6d021e15/0.2.1`) and drift triage

```
recon selftest                      # PASS: 9 canonicalization rules exercised
recon run --unit U5 --family oracle \
  --mapping <U5 subset of .migration/03_mapping_spec.json>   # see note
  --tolerances .migration/02_tolerances.json \
  --canonicalization .migration/canonicalization.json --mode live \
  --source-dsn-secret OW_BILLING_FIXTURE_DSN --target-uri-secret MONGODB_ATLAS_URI \
  --target-db ow_tp_mongodb_205236 --seed 714559852 --param batch_no=85559852 --param source_ns=demo \
  --out wave2a_evidence/U5/gate_run1   # pre-existing load (child's, 00:35Z)  -> FAIL (1 Tier-1 finding)
  --out wave2a_evidence/U5/gate        # after reload from head 1aefd226      -> PASS (authoritative)
```

Mapping note: the harness iterates every collection in the file it is given, so the unit gate is fed the unit's
collections. `wave2a_evidence/U5/mapping_u5_subset.json` was generated **mechanically** from
`.migration/03_mapping_spec.json` at the head (all top-level keys retained, `collections` filtered to
`unit == "U5"`); it is byte-for-byte the child's `.migration/recon/U5/mapping/u5.json` minus the child's
informational `projection_note` key. Input hashes at head `1aefd226` (identical on the run branch `1a8c26f7`):
`03_mapping_spec.json` `57de55f2…7bb45`, `02_tolerances.json` `d67ccdda…4ada7`, `canonicalization.json` `527cf87c…3eb9`.

**Run 1 (pre-existing load): FAIL** — Tier 1 `billing_audit_log root_count: rows(BILLING_AUDIT_LOG)=1 vs docs=0`.
Tiers 2/3 not reached (harness stops at the failing tier).

Drift-vs-defect triage (source side re-run twice, 2 s apart, `drift_source_recount.json`): all 11 tables
identical both passes (69/0/814/3/3/3/2/5/1/1/**1**); `FIXTURE_META` unchanged. The audit row: `LOG_ID=1`,
`LOGGED_AT 2026-09-01 22:53:00`, `MODULE=PLANS`, `MESSAGE=fn_list_plans`, `SCN_TO_TIMESTAMP(ORA_ROWSCN)`
2026-09-01 22:52:58 — 2 h after seeding, matching the wave-0 recon window (its report notes "two PL/SQL calls").
`USER_SOURCE` confirms the only writer is `PKG_OW_UTIL` (`INSERT INTO billing_audit_log`), called from the
packages' public functions. Classification: **DRIFT (observer-induced source mutation), not a defect** — the
loader copies the table verbatim (`root_where: null`) and the child's load predates the row on its own fixture.
Per the brief the unit was re-loaded from the head and re-gated.

**Run 2 (after reload): PASS** — Tier 1 `counts_through_mapping` 11 checks; Tier 2 `per_field_aggregates` 53
checks (24 string/id fields deferred to Tier 3 as designed); Tier 3 `keyed_diffs` 902 checks, `full_diff` on all 9
collections (populations 69/0/814/3/3/5/1/1/1), embeds graded `rating_periods.results` 3 and
`billing_invoices.lines` 2; `warnings: []`. Identical to the child's committed `result.json` except
`generated_at` and Tier-3 `checks_run` 901→902 (the audit row). Tier 4 does not apply (D10: PL/SQL packages are
rewritten in U6–U9; no recorded ops file) — app-level parity replayed by hand in §3.

## 2. Load state and head attestation

- Branch `tp-run/mongodb-20260901T205236Z--u5` head = `1aefd226d917ec0ddd604159ce7196b924050f7e`
  (committed 00:37:13Z; `git ls-remote` re-checked after the run). Not an ancestor of the run branch (PR #1438 open).
- The child's committed load (`load_report.json`, 00:35:36→00:35:44Z) predates the head commit by ~100 s; the
  head's last change to `load_u5.py` drops a redundant staging-name assertion (read before running — no
  transform/grading logic touched). Per the brief I re-ran the loader from the head into the target
  (`load_report.recon.json`) and graded that state. Loader read (read-only on Oracle, secrets by name, target-db
  pinned to `ow_tp_mongodb_205236`, `Int64`/`Decimal128` typed, staging collection + `rename(dropTarget)` per
  collection, aborts on orphan children, count/ns assertions before swap).
- My load report == the child's on all 9 collections except `billing_audit_log` (`source_rows/inserted/docs_after/
  ns_docs_after` 0→1). Unit tests at head: `scripts/tp_mongo/tests/test_load_u5.py` 8 passed.

## 3. Adversarial probes — 142 probes, 142 ok (`probe_u5.py`, `probes.json`)

| Area | Probe | Result |
|---|---|---|
| Keys | key-set equality src↔tgt on all 9 collections (897 roots) | ok |
| Values | independent full value diff, every field, `TO_CHAR` text → canonical strings (no float path) | ok — 0 diffs |
| Nulls | src NULL count == tgt explicit-null count, 0 missing keys (D2) | ok — only `subscriptions.ends_on` 69, `suspended_on` 68 are NULL anywhere |
| Shape | field-set audit (exactly mapping fields + `_id` + `ns` [+ embed array]) | ok |
| Shape | BSON `$type` per field == declared `bson_type` (or null) on 100 % | ok (`long` via `Int64`, `decimal` via `Decimal128`) |
| Keys | no duplicate natural ids; `_id` == natural id bijection | ok |
| Rules | no empty strings in string fields (`empty_string_is_null`) | ok |
| Embeds | per-parent array length == child rows (`results` {1,1,1}; `lines` {2,0,0}); histogram equal | ok |
| Embeds | element-level full value diff + element field set; element `id` globally unique; `lines` sorted by `line_no` | ok |
| Embeds | orphan children in source (loader would abort) | ok — 0 |
| Aggregates | exact sums for `lines.amount`, `results.*_units`, `results.overage_amount`; sum/min/max of `subtotal/tax/total/amount/remaining_amount/units`; distinct tenants | ok |
| Doc-level | per-invoice (`subtotal`, Σ`lines.amount`) relationship identical both sides (invoice 1: 149.00 vs 161.29 in the *source* too — lines include the usage line; faithful copy) | ok |
| Boundaries | min/max doc by every numeric/date column, full-field compare; both sides' extremes agree | ok |
| Empty | `subscriptions_history` exists, 0 docs, `_id_` only; `billing_audit_log` 1 doc == the observer row, `log_id` long | ok |
| Indexes | declared keys/`unique`/TTL present exactly on all 9; no extras; no `*__staging` residue | ok |
| Validator | `$jsonSchema` strict/error present; rejects `units=0`, `units=-1`, wrong `ns`, int32 `units`; count unchanged | ok |
| Validator | `kind_cd` ⊂ `codes USAGE_KIND` (data holds; FK half of the trigger not in validator — declared) | ok |
| Quarantine | no U5 collections in the quarantine db (none expected; expected 0 == observed 0) | ok |
| Cross-unit | see §4 (16 probes) | ok |
| Replay | see §4 (8 probes, 386 ops) | ok |

Source unchanged by my probes: `BILLING_AUDIT_LOG` still 1 row / `SEQ_BILLING_AUDIT_LOG` still 2 afterwards
(all replays are plain SQL, no PL/SQL invocation).

## 4. Cross-unit consistency and app-level replay

- `tenants` (69) and `plans` (3) target id sets == source. `tenant_id` sets on `subscriptions` (69),
  `usage_events` (69), `rating_periods` (1), `billing_invoices` (3), `credit_notes` (3), `dunning_attempts` (1),
  `notifications` (1) equal source and resolve 100 % to `tenants` (same as in the source). `subscriptions.plan_id`
  ⊂ `plans` 3/3. One subscription per tenant (69×1) both sides.
- Code domains: `subscriptions.status_cd` {10,20} ⊂ `SUB_STATUS`; `billing_invoices.status_cd` {20,40} ⊂
  `INV_STATUS`; `dunning_attempts.status_cd` {20} ⊂ `DUN_STATUS`; `notifications.kind_cd` {2} ⊂ `NOTIF_KIND`;
  `usage_events.kind_cd` {1,2,3} == `USAGE_KIND`. `codes` types in target ⊇ source types.
- Internal refs: `billing_invoices.period_id` ⊂ `rating_periods` (== source resolution), `dunning_attempts.invoice_id`
  ⊂ `billing_invoices`, `results[].subscription_id` ⊂ `subscriptions`, `results[].period_id` and
  `lines[].invoice_id` == parent `_id`.
- Replays (Oracle SQL lifted from `USER_SOURCE` vs Mongo find/aggregate), identical result sets:
  `PKG_RATING.fn_usage_summary` (kind, count, Σunits per tenant × 4 windows) 160 ops; `PKG_PLANS.fn_entitlement`
  (latest covering subscription ⋈ plans, 69 tenants × 3 dates) 207 ops; `PKG_DUNNING.fn_overdue_accounts`
  (status 40, issued before as-of, tenant status label, days overdue) 4 as-of dates; `PKG_INVOICING.fn_invoice_lines`
  3 invoices; `PKG_RATING` rollover window (prior 3 months' `rollover_units`) 9 ops; `PKG_INVOICING` credit-note
  application order (`remaining_amount > 0` by `issued_on, id`) 3 tenants; `sp_schedule_dunning` read half (next
  `attempt_no` per status-40 invoice: 1 and 2) and `sp_suspend_overdue` read half (kind-3 notification existence).

## 5. Cost line (this reviewer, parent machine, serial)
| Unit | Gate wall-clock | Reload | Probe wall-clock | Source passes | Target reads |
|---|---|---|---|---|---|
| U5 | run 1 1.9 s (00:46:45→47) · run 2 12.0 s (00:47:58→48:10) | 9.7 s (00:47:37→47) | 44.7 s (00:53:54→54:40) + 2 earlier partial passes (probe-script fixes) | 2 gate passes (11 COUNT + 53 agg + full keyed fetch) + 1 loader pass (11 SELECT) + 2 drift recounts + 1 probe pass (~700 statements) | full scans of 9 collections ×~4, 4 rejected inserts |
Setup: reused the wave-1 venv/harness (`recon selftest` PASS); no fixture restart or reseed was needed (all containers healthy).

## 6. Grading-only amendments (described, NOT applied)
1. **None required for the verdict.** The gate is green as specified after grading the head's load state.
2. For the orchestrator's consideration (decision-log / profile feedback, not tolerance changes):
   - Record in `05_decisions.md` that reviewer probes must not invoke `PKG_*` PL/SQL against the live fixture
     (they write `BILLING_AUDIT_LOG`); the 1-row delta vs the census is now part of the live baseline and any
     later unit gating `billing_audit_log` (U6 replay set) should expect 1, not 0.
   - Spec text for #35 says validator `units >= 0`; the trigger and the loader both enforce `> 0`. Suggest
     aligning the mapping note to `units > 0` (documentation only; the loader is right).
   - `counters` seeds for `SEQ_SUBSCRIPTIONS_HIST`/`SEQ_BILLING_AUDIT_LOG`: whichever unit writes them (U6/U9) must
     seed from `USER_SEQUENCES.LAST_NUMBER` at cutover (now 1 / 2), mirroring U1's D11 approach.
