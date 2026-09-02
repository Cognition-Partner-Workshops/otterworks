# Independent audit countersignature v2 (re-audit) — OtterWorks billing estate → Atlas `ow_tp_mongodb_205236`

Run `tp-run/mongodb-20260901T205236Z` @ watermark `74ecd69e98876b8da26336a6d7cc24eba3e74697` · evidence pack
`--cutover-prep:.migration/08_evidence_pack.md` **v3** (`e1dd1a15`) · runbook `--cutover-prep:docs/tech-partnerships/cutover-runbook-mongodb-205236.md`
(v3) · parallel-run evidence `--parallel-run-v2` @ `2443d6f5bcf6f93445a2ee14226edb677af943a4` (header pin `de03da97`).
Prior countersign attempt: `countersign.md` (verdict FINDINGS, F-A-1…F-A-4). This re-audit re-ran only what those findings
touch plus the U8 gate, on a freshly booted VM, working from the v3 pack alone (no child-session diagnoses or PR threads read).
The audit session performed no migration work, changed nothing outside `.migration/recon/audit/`, and wrote to Atlas only the
`replay_u8_*` clone reset inside `ow_tp_mongodb_205236` (the unit's own loader, the same reset the graders perform). Legacy
sources were read with plain SQL / scans only; `source_pre.json` == `source_post.json` on every value.

## Verdict: **COUNTERSIGNED**

Every re-run gate reproduces the pack's recorded value (U0 Tier 1–3, U8 Tier 1–4 incl. the PKG_INVOICING money-path replay),
using a harness installed **from the pack's citation alone** and identity-verified before running. The one deliberately
re-run divergent gate (U5 Tier 1 on a clean fixture) reproduces exactly the behaviour the v3 pack and runbook now disclose,
and is no longer a hidden dependency of the runbook. Findings F-A-1…F-A-4 are each closed or carried as an explicit STOP C line
(§H.6, §H.7). No high-severity finding remains; three LOW items below are informational and need no action before STOP C.

## 1. Environment (independently booted on this audit VM)

| Item | Observed | Expected (pack / 00_context) | Match |
|---|---|---|---|
| Boot | `sudo -n systemctl stop postgresql`, `make infra-up`, `make seed-legacy NS=demo`, `make oracle-billing-up`, `make oracle-billing-seed NS=demo` (worktree at `74ecd69e…`) | as `00_context.md` | yes |
| `sha256sum testdata/legacy/manifests/demo.json` | `0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89` | same | yes |
| `make seed-legacy-validate NS=demo` | 15/15 | 15/15 | yes |
| Oracle `BILLING_AUDIT_LOG` rows / `SEQ_BILLING_AUDIT_LOG` | 0 / 1 (clean fixture) | pack watermark 1 / 2; **v3 discloses** the clean-fixture values (runbook "Tooling write to legacy", §H.7) | as disclosed |
| Frozen artefacts | mapping v1.0.1, tolerances v1, canonicalization v1 read from `74ecd69e…` (result.json: `mapping_version v1.0.1`, `tolerance_version v1`) | same | yes |

### Harness — installed from the pack's citation alone (closes F-A-1)

| Check (pack §1 / `01_conventions.md` "Recon harness") | Result |
|---|---|
| `git clone` plugin repo, `checkout 8d4f787151ad460659d139c081ddc1284c08552c` | ok |
| git tree id of `skills/mongo-recon-harness/harness` == `acd098ea3979c8a126e504445d99f91b7008bf7e` | **match** |
| package file count 13 | **match** |
| content sha256 of sorted `<sha256>  <path>` manifest == `ddaaeec35359b2bee98989a2b49de4b5aff63cdedea5edf7384a031c03dddabb` | **match** with paths relative to the plugin repo root (`skills/mongo-recon-harness/harness/…`), `LC_ALL=C` sort. Paths relative to the harness dir or skill dir do **not** match (`d6a1262f…`, `f20dddab…`) — see F-B-2 |
| `pyproject` version 0.1.0 | match |
| `recon selftest` | `PASS: 9 canonicalization rules exercised` (same line the evidence log cites) |
| `--allowed-targets-file` | rejected by the pinned build (flag omitted); allowlist "consumed by hardened builds, ignored by the pinned build" as `01_conventions.md` states — consistent |
| Cache label `6d021e15/0.2.1` vs pinned package | still a different program: 9 files differ, cache-only `recon/paths.py` (`evidence_v2/harness_cache_vs_pinned.diff.txt`). Confirms the pack's warning that the label is not an identifier |

Tools `subset.py`, `source_check.py` verbatim from `--parallel-run-v2:.migration/recon/parallel_run/tools/`.

## 2. Gates re-run (all `--mode live`, seed `714559852`, `batch_no=85559852`, `source_ns=demo`, pinned harness)

| Unit / family | Gate | This re-audit | Pack cycle 3 (`--parallel-run-v2:…/evidence/cycle3/<U>/gate/`) | Match |
|---|---|---|---|---|
| U0 Oracle (`codes`,`tenants`,`plans`) | T1/T2/T3 | 3 / 14 / 104 PASS; pop 32 / 69 / 3 | 3 / 14 / 104 PASS | **yes** |
| U8 PKG_INVOICING (clone reset + replay) | T1/T2/T3/**T4** | 8 / 36 / 902 / **6 PASS**; embeds `rating_periods.results` 3, `billing_invoices.lines` 2 graded; `tier4_provenance`: `transcripts_match true`, `oracle_source_sha 0d326cad54d94cd64e8abb53585b37436eaad2193fdc15ba3596fbb8db3f0d55` | 8 / 36 / 902 / 6 PASS; same sha | **yes** |
| U5 Oracle billing core — **informational re-run of the F-A-2 divergence** | T1 | 11 checks, FAIL (1): `billing_audit_log` rows 0 vs docs 1; T2/T3 not reached | 11 / 53 / 902 PASS at the watermark; v3 pack + runbook state a clean fixture yields exactly this | matches the **disclosed** clean-fixture behaviour; not a parity defect (target was loaded from and graded against the post-probe source, which the pack documents) |
| Source stability | `source_pre` vs `source_post` | identical on all Oracle/Postgres/DynamoDB counts, sequences, `FIXTURE_META` | source pre == post every cycle | yes |

`guards.py` (count guard 18/18) was not re-run: it requires all ten units' `result.json` and only U0/U5/U8 were gated this pass.

## 3. Disposition of prior findings

| ID | Prior severity | v3 closing edit checked | Status |
|---|---|---|---|
| F-A-1 | HIGH | Pinned by plugin commit + tree id + content sha256 in pack §1, `01_conventions.md`, evidence-log header (`de03da97`, header-only: diff `2443d6f5..de03da97` touches 3 lines in `evidence_log.{md,json}` and `build_evidence.py`, no evidence bytes). `.migration/allowed_targets.json` = `{"databases": ["ow_tp_mongodb_205236","ow_tp_mongodb_205236_quarantine"]}` present on `--cutover-prep`. Re-grade under the hardened harness carried as STOP C **§H.6** (recommendation NO). Verified: harness re-installed from the citation alone reproduces U0 and U8 exactly | **CLOSED** (see F-B-1 for the allowlist's branch location) |
| F-A-2 | MEDIUM | Runbook D.2 captures `S_<seq>` / `A0` from the live `USER_SEQUENCES` / `BILLING_AUDIT_LOG` read at freeze; D.4, E.1, E.4, E.5 phrase expectations as `S`, `S+2`, `A0`, `A0+2` with the 2026-09-02 values quoted only as "observed". Disclosure section "Tooling write to legacy during the engagement" at the top of the runbook; explicit acknowledgement line **§H.7** ("no" blocks the window). U5 T1 re-run confirms the disclosed clean-fixture values | **CLOSED as disclosed** + STOP C line |
| F-A-3 | MEDIUM | Runbook line 6–7: every write to the production target or any legacy store is CUSTOMER-executed, "including the E.4 transcript replays and the G.3 clone drop". D.9 executor: CUSTOMER (E.4) + DEVIN (E.1–E.3, first-cycle recon, E.5 read-only). §E.4 header "executor **CUSTOMER**". G.3: CUSTOMER executes the drops, Devin lists/confirms read-only. Every other DEVIN-executed row (D.2, D.3, D.4, F.3.5) is a read of legacy/target plus writes to the evidence branch (`mongoexport`, `source_check.py`, `guards.py`) | **CLOSED** |
| F-A-4 | LOW | Pack, runbook, `04_progress.md`, evidence-log header: all commit heads 40-char (only `…`-truncated file sha256s and the seed remain short, by design) | **CLOSED** (`05_decisions.md` still carries 8-char heads — F-B-3) |

## 4. Findings (this re-audit)

| ID | Severity | Finding | Evidence | Effect on STOP C |
|---|---|---|---|---|
| F-B-1 | LOW | Pack §1/§6 and runbook §H.6 say `.migration/allowed_targets.json` was "added to the run branch" / "now added". It exists only on `--cutover-prep` (base `74ecd69e…`, 12 commits, unmerged); it is absent at `74ecd69e…` and at the run-branch head `cfd80e63…`. The pinned harness ignores it, so this has no effect on any verdict; it matters only once the hardened harness is used (§H.6 = NO). | `git ls-tree` on the three refs | none; wording becomes true when `--cutover-prep` merges into the run branch |
| F-B-2 | LOW | The content-hash recipe ("sorted `<file sha256>  <path>` manifest of the 13 package files") does not state the path base. It reproduces only with paths relative to the plugin repo root under `LC_ALL=C`; other natural readings give different digests. The tree id `acd098ea…` is unambiguous and also matched. | §1 table | none; suggest the pack states "paths relative to the plugin repo root" |
| F-B-3 | LOW | `05_decisions.md` (run branch and `--cutover-prep`) still quotes 24 heads at 8 chars; the F-A-4 closing edit did not claim that file. No mismatch found. | `grep` on `05_decisions.md` | none |

## 5. Not checked

- U1, U2, U3, U4, U6, U7, U9 gates and the U1/U2/U3 quarantine-set comparison were **not** re-run this pass (they matched in
  the prior countersign and no finding touched them); U5 Tier 2/3 not reached (T1 FAIL, as disclosed); count guard not re-run.
- Ledger vs merges and wave-head citations were not re-derived (verified OK in the prior countersign; the run branch gained
  one non-merge commit `cfd80e63` — decision row 21 + `cutover_workflow.py` — after the watermark, not re-audited here).
- The hardened harness (`65aa799…`) was not run against the frozen mapping; §H.6 records that it rejects it.
- No HTTP route, `legacy-billing` application, RPT-114 endpoint, Atlas index/TTL/validator state, or quarantine document
  contents were exercised. No production system, credential, or deployment configuration was touched or inspected.
- Child-session diagnoses and PR review threads were not read (per brief).

Raw artefacts: `evidence_v2/{U0,U5,U8}/` (`gate/result.json`, `report.md`, `recon.summary.md`, U8 `tier4_provenance.json`,
`load_report.json`, stdout logs), `evidence_v2/source_pre.json`, `source_post.json`, `harness_cache_vs_pinned.diff.txt`.
