# Independent audit countersignature — OtterWorks billing estate → Atlas `ow_tp_mongodb_205236`

Run `tp-run/mongodb-20260901T205236Z` @ `74ecd69e` · evidence pack `--cutover-prep:.migration/08_evidence_pack.md` (v2) ·
parallel-run evidence `--parallel-run-v2` @ `2443d6f5` · runbook `--cutover-prep:docs/tech-partnerships/cutover-runbook-mongodb-205236.md`.
Audit session performed no migration work, changed nothing outside `.migration/recon/audit/`, and wrote to Atlas only
inside `ow_tp_mongodb_205236` (replay clones `replay_u7_*` / `replay_u8_*`, re-created by the units' own clone loaders
before their Tier-4 replays — the same reset the wave graders performed). Legacy sources were read with plain SQL /
scans only; `source_pre.json` == `source_post.json` on every count, sequence and `FIXTURE_META` value.

## Verdict: **FINDINGS**

Not countersigned as-is. 7 of 8 re-run gates reproduce the pack's recorded values exactly (U0, U1, U2, U3, U4 Tier 1–3;
U7 and U8 Tier 1–4 including the money-path replays; all three quarantine sets). One gate (U5 Tier 1) does **not**
reproduce against a freshly seeded deterministic fixture (F-A-2), and the harness distributed today cannot grade the
frozen mapping at all (F-A-1, high). Ledger, wave-head citations, and the runbook's scope statement check out; the
runbook has two steps where Devin writes to the production target (F-A-3).

## 1. Environment (independently booted on the audit VM)

| Item | Observed | Expected (pack) | Match |
|---|---|---|---|
| Boot | `sudo -n systemctl stop postgresql`, `make infra-up`, `make seed-legacy NS=demo`, `make oracle-billing-up`, `make oracle-billing-seed NS=demo` | as `00_context.md` | yes |
| `sha256sum testdata/legacy/manifests/demo.json` | `0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89` | same | yes |
| `make seed-legacy-validate NS=demo` | 15/15 | 15/15 | yes |
| Oracle `CUSTOMER_MASTER / INVOICE_HEADER / INVOICE_LINE / ENTITY_ATTR_VALUE` | 25,000 / 18,750 / 150,000 (37 orphans) / 8,333 | same | yes |
| Postgres `documents` / DynamoDB `ns=demo` | 2,000 / 10,000 | same | yes |
| Oracle `BILLING_AUDIT_LOG` rows / `SEQ_BILLING_AUDIT_LOG` | **0 / 1** | pack source watermark **1 / 2** | **no** (F-A-2) |
| `FIXTURE_META.INITIALIZED_AT` | 2026-09-02 07:32:36 (this VM) | 2026-09-01 20:53:10 (parent VM) | n/a — excluded object, expected to differ |
| Frozen artefacts sha256 | mapping `57de55f2…7bb45` (v1.0.1), tolerances `d67ccdda…4ada7` (v1), canonicalization `527cf87c…3eb9` (v1) | same three files, unchanged on run head | yes |

Harness: installed from `/opt/.devin/plugins/cache/github.com_Cognition-Partner-Workshops_mongo-migration-plugin-6d021e15/0.2.1/skills/mongo-recon-harness/harness`
as instructed. **That build fails every gate before connecting** (see F-A-1). The re-runs below were therefore executed
with the harness pinned to plugin commit `8d4f787151ad460659d139c081ddc1284c08552c` (last commit before the 2026-09-02
hardening series; `recon selftest PASS: 9 canonicalization rules exercised`, the same selftest line the evidence log
cites). Everything else — mapping projection (`tools/subset.py`), flags, seed/params, `recon_ext` drivers, `guards.py`,
`source_check.py` — is verbatim from `--parallel-run-v2:.migration/recon/parallel_run/tools/` (guards.py: one path edit
to point at this checkout's `03_mapping_spec.json`). Driver script: `evidence/run_gates.sh`.

## 2. Gates re-run (sampled; all `--mode live`, seed `714559852`, `batch_no=85559852`, `source_ns=demo`)

| Unit / family | Gate | This audit | Pack cycle 3 (`evidence/cycle3/<U>/gate/`) | Match |
|---|---|---|---|---|
| U0 Oracle (`codes`,`tenants`,`plans`) | T1/T2/T3 | 3 / 14 / 104 PASS; pop 32/69/3 | 3 / 14 / 104 PASS | yes |
| U1 Oracle (`customers`,`customers_history`) | T1/T2/T3 | 3 / 313 / 33,333 PASS; pop 25,000/0 | 3 / 313 / 33,333 PASS | yes |
| U2 Oracle embedded lines (`invoices` + `lines[]`) | T1/T2/T3 | 2 / 9 / 168,713 PASS; pop 18,750 | 2 / 9 / 168,713 PASS | yes |
| U3 Postgres (`documents`,`document_snapshots`) | T1/T2/T3 | 3 / 18 / 16,260 PASS; pop 2,000/384 | 3 / 18 / 16,260 PASS | yes |
| U4 DynamoDB (`files`) | T1/T2/T3 | 1 / 12 / 10,000 PASS; pop 10,000 | 1 / 12 / 10,000 PASS | yes |
| U5 Oracle billing core (9 collections) | T1 | 11 checks, **FAIL (1)**: `billing_audit_log` rows(BILLING_AUDIT_LOG)=0 vs docs=1; T2/T3 not reached | 11 / 53 / 902 PASS | **no** (F-A-2) |
| U7 PKG_RATING (clone reset + replay) | T1/T2/T3/**T4** | 5 / 23 / 892 / **8 PASS** | 5 / 23 / 892 / 8 PASS | yes |
| U8 PKG_INVOICING (clone reset + replay) | T1/T2/T3/**T4** | 8 / 36 / 902 / **6 PASS** | 8 / 36 / 902 / 6 PASS | yes |
| Quarantine U1 | classes / rate | `dirty_signup_dt` 50 + `bad_csv_list` 31 = 81 / 25,000 = 0.324 % | same | yes |
| Quarantine U2 | classes / rate | `invoice_feed_orphan_lines` 37 / 18,750 = 0.197 % | same | yes |
| Quarantine U3 | classes / rate | `orphan_document_snapshots` 6 / 2,384 = 0.252 % | same | yes |
| Quarantine DB | collection set | exactly the 4 declared classes; `ns_docs == total_docs` for each | same | yes |
| Count guard (`guards.py`) | ns-scoped == total == source | 17/18 equal; `billing_audit_log` ns=1 total=1 vs source 0 | 18/18 | **no** (same root cause as U5) |

Tier-3 populations, tier check counts and verdicts for the 7 matching units are identical to cycle 3; raw
`result.json` / `recon.summary.md` / `report.md` per unit, `guards.json`, `source_pre.json`, `source_post.json` are
under `evidence/`.

## 3. Ledger, wave heads, runbook

- **Wave reports cite the exact graded head.** Every merge on the run branch has as second parent the head each wave
  report grades: U0 `892eb88a` (#1423), U1 `c5baa80a` (#1430), U2 `9e73ffea` (#1432), U3 `dfa5e978` (#1420), U4
  `3420f475` (#1419), U5 `1aefd226` (#1438), U6 `f463577b` (#1440), U7 `f05741f3` (#1439), U8 `0024b45e` (#1447),
  U9 `9f67ec79` (#1444), fix pass `7791a93e` (#1457, merge `5fe2af81`). Checked with `git rev-parse <merge>^2` against
  the 40-char SHAs in `wave0/wave1/wave2a/wave2b/wave3/fix_pass.md`. **OK.**
- **`04_progress.md` matches the merges.** 11 PR merges on `tp-run/mongodb-20260901T205236Z` (first-parent log),
  same PR numbers and heads as the ledger; run head `74ecd69e` is the ledger commit after the fix-pass merge. **OK.**
- **Runbook scope in first section:** §A "Scope — what this repoint covers and what still reads legacy" with A.1
  covered / A.2 still-legacy tables and the explicit "partial-scope cutover" statement. **OK.**
- **Runbook executors:** every step in D, F.3 and G carries an executor. All freeze/secret/DNS/flag/scheduler steps
  (D.1, D.5–D.8, D.10–D.12, F.3.1–F.3.4, F.3.6, G.1–G.2, G.4–G.7) are CUSTOMER. Two steps have DEVIN writing to the
  production Atlas database — see F-A-3.

## 4. Findings

| ID | Severity | Finding | Evidence | What it means for STOP C |
|---|---|---|---|---|
| **F-A-1** | **HIGH** | The recon harness as currently distributed cannot re-grade the frozen evidence. Plugin cache `mongo-migration-plugin-6d021e15/0.2.1` (content = plugin repo `65aa799`, hardened 2026-09-02 03:43–05:14 UTC) (a) refuses to start without `.migration/allowed_targets.json`, which does not exist on the run, cutover-prep or parallel-run branches, and (b) rejects mapping v1.0.1 with `ConfigError: object <c> has root_where but no target_where` for `customers` (U1), `invoices` (U2), `document_snapshots` (U3), `files` (U4). The evidence pack and evidence log identify the harness only as `6d021e15/0.2.1`, a label that now denotes a different program from the one that produced the PASS verdicts. | first run in `evidence/run_gates.sh` with the cache install: all 8 gates exit 1 pre-connection (`stdout.log` excerpts in §1); re-run succeeded only after pinning to `8d4f787` | The gating authority is not reproducible from its cited identifier. Before STOP C the pack should pin the harness by commit/content hash (and the customer should decide whether the frozen mapping must be re-graded under the hardened harness, which requires `target_where` on 4 objects plus an allowlist — a mapping-shape change outside this audit's remit). This audit did **not** fix either. |
| **F-A-2** | **MEDIUM** | The watermark is not reproducible from the deterministic fixture. A fresh `make oracle-billing-seed NS=demo` yields `BILLING_AUDIT_LOG` = 0 rows and `SEQ_BILLING_AUDIT_LOG` = 1; the graded source and the Atlas target hold 1 row (`log_id 1`, `PLANS/fn_list_plans`, 22:52:58Z) and counter 2. The pack discloses this (row 23 "1 live observer row"; wave2a §0 "DRIFT (observer-induced source mutation)") and disposes it accepted-as-is, but it is a write to the read-only legacy source by a recon probe (guardrail 1), and it propagates: U5 T1 fails on a clean fixture, the count guard is 17/18, and runbook D.4 hard-codes `seq_billing_audit_log == 2` as an abort condition. | `evidence/U5/gate/recon.summary.md`, `evidence/guards.json`, `evidence/source_pre.json` (`BILLING_AUDIT_LOG` 0, `SEQ_BILLING_AUDIT_LOG` 1) vs cycle-3 `source_post.json` (1 / 2) | Not a defect in the loader or the target; the pack's numbers are correct for the mutated parent fixture. For production, D.2/D.4 must derive expected counter values from the live `USER_SEQUENCES` read, not from the fixture literals in the runbook. The customer should be told explicitly that one Oracle row was written by tooling during the engagement. |
| **F-A-3** | **MEDIUM** | Runbook line 6 states "every production-touching step below is executed by the customer-held cutover principal", but D.9 has DEVIN as co-executor while E.4 replays append 2 `billing_audit_log` rows and advance `counters` in the production database, and G.3 has DEVIN dropping `replay_u6..u9_*` collections from `ow_tp_mongodb_205236`. Both are Devin writes to the production target. | runbook §D row D.9 ("read-only except the audit rows produced by E.4's replay"), §E.4, §G row G.3 | Either reassign D.9/E.4 execution and G.3 to CUSTOMER, or amend line 6 and §B.6 to state the two Devin write paths explicitly, so STOP C is decided on an accurate principal model. |
| F-A-4 | LOW | `04_progress.md` and the pack quote unit heads at 8 chars; the wave reports carry the 40-char SHAs. No mismatch found, informational only. | §3 | none |

Carried-forward items from the pack (F-U8-2/F-U7-1 period-id acceptance, partial application scope A.2,
F-U9-2 deployment wiring) were not re-adjudicated; they are customer decisions already on the STOP C sheet.

## 5. Not checked

- U6 (PKG_OW_UTIL/PKG_PLANS) and U9 (PKG_DUNNING) gates were not re-run; U5 Tier 2/3 was not reached (T1 FAIL).
- Mutating transcripts were graded only via the U7/U8 Tier-4 drivers on the replay clones; no HTTP route or the
  `legacy-billing` application was exercised; no RPT-114 endpoint parity.
- Child-session diagnoses and PR review threads were not read (per brief); PR merge state was verified from git
  history only, not from the PR API.
- Cycles 1 and 2 of the parallel run were not re-derived; comparison is against cycle 3 only.
- Atlas index/validator/TTL state, Atlas M0 sizing, and quarantine document contents (only classes and counts).
- No production system, credential, or deployment configuration was touched or inspected.
- The hardened harness's own selftest and unit tests were not evaluated for correctness; F-A-1 records that it rejects
  the frozen inputs, not whether its stricter rules are right.
