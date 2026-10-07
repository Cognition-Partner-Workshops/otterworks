# Run report — `mmp_rt_b4_oracle` (hand-back, plan step `s6.3-run-report`, UNT8-21)

Hand-back of the unattended plugin-validation run of the `mongo-migration` Devin plugin against the OtterWorks legacy Oracle billing estate (`services/legacy-billing/db/oracle/**`, schema `OW_BILLING`). This is the last ticket of the run: it reports, tears nothing down, and opens no database connection — every number below is read from an artifact already merged on the run branch, from the verifier branch (`git show` only), or from `git ls-remote`. The findings record of the run is [`05_decisions.md`](05_decisions.md) (every section linked in §9) and the diff against the prior run is [`06_prior_run_diff.md`](06_prior_run_diff.md); this file is the index that points at them.

## 1. Identity

| item | value |
|---|---|
| run branch | `tp-run/mongodb-20261007T161014Z` on `Cognition-Partner-Workshops/otterworks`, cut off `tech-partnerships` @ `32baffd8`; tip at report time `a1611288` (#1940 merged); this report is the next and final PR |
| plugin under test | `Cognition-Partner-Workshops/mongo-migration-plugin` @ **`353280fc837193a40ccc005cb62fb4ffaf8ac16f`** (its `main` tip, merge of plugin PR #57, 2026-10-07T14:57:49Z), cloned to `~/mmp`, used unpatched, never pushed to (§8) |
| source | Oracle Free fixture container `otterworks-oracle-billing-oracle-billing-1` on the fixture host, schema `OW_BILLING`, `mmprt` mini seed + package exercise ([`fixtures/mmprt-mini.json`](fixtures/mmprt-mini.json), PR #1914); DSN by name `MMP_RT_SRC_DSN`, query concurrency 1 |
| target | Atlas via secret `MONGODB_ATLAS_URI` (name only); database `mmp_rt_b4_oracle` only ([`allowed_targets.json`](allowed_targets.json)); budget 10 MB; nothing dropped at any point |
| `mapping_version` / `mapping_sha256` | **`map-v1.1`** / **`3dc4060d3a4bdc39f0904c3e79eff2568fb32e5560cad822280a0aa95b2539b6`** ([`mapping_spec.json`](mapping_spec.json); `map-v1` was `949a8891f7fe837ad528d3f8aa54575e0fb50c71346c581310457855540201b2`, version bump only — `05_decisions.md` §3b.3). Recomputed with `sha256sum` on `a1611288` for this report: matches |
| `tolerance_version` / sha256 | **`tol-1`** / **`a23d517a8e6d00c84f668c0016ef0e42b16625d45ab7e4166e3838abf241e3da`** ([`recon_tolerances.json`](recon_tolerances.json): `numeric_abs_tol 0`, `aggregate_rel_tol 0`, exact parity). Recomputed on `a1611288`: matches |
| wave-1 `manifest_sha` | **`55e68257b3f9`** — stamped on all four batch results ([`recon/w1-*.json`](recon/)) and on the verifier record; no `.migration/waves/` file exists on the run branch (F59, still present) |
| mode | every unit recon `--mode live`, `target_class migration_cluster`; `redaction_salted: false` on all 20 `result.json` (P9) |

## 2. PRs of this run (merge order from `git log --first-parent 32baffd8..origin/tp-run/mongodb-20261007T161014Z`, re-read for this report)

| PR | ticket | plan step | merged sha | what landed |
|---|---|---|---|---|
| — (direct push) | UNT8-3 | s1.3-allowlist | `b4615076` | `allowed_targets.json` write scope `mmp_rt_b4_oracle`. Pushed directly: the org dbx guard rejected the PR path (`05_decisions.md` §5b P1) |
| #1914 | UNT8-2 | s1.1-fixture | `0b6cf526` | `mmprt` mini Oracle fixture: seed wrapper, package exercise, manifest |
| #1915 | UNT8-5 | s1.4-tolerances | `8e7dee51` | `recon_tolerances.json` `tol-1` (exact parity) |
| #1916 | UNT8-4 | s1.3 (guard) / s1.2 | `25083532` | `allowed_targets.json` `guard_mode: warn` + `catalogs` compat key so the plugin probe scripts can run (P1) |
| #1917 | UNT8-4 | s1.2-connectivity | `a0477e2e` | `connectivity.json` — online, live × migration_cluster, `privilege_excess` both sides accepted (P2) |
| #1919 | UNT8-6 | s2.1-census | `8ac32f2b` | `census.json`, `census_ddl.json`, `census_diff.json`, `01_census_crosscheck.md`, fixture manifest |
| #1921 | UNT8-9 | s3.1-access-scan | `a29063bb` | raw `access_patterns.json`, `03_access_scan_notes.md` |
| #1922 | UNT8-7 | s2.5-data-profile | `ff5966d8` | `data_profile.json` (173 stats), `02_profile_gaps.md` |
| #1923 | UNT8-8 | s2.3-dependency-register | `5161a8a6` | `02_dependency_register.md` |
| #1924 | UNT8-22 | s3.1b-app-scan | `2890ade9` | rescan with app + ETL caller roots |
| #1925 | UNT8-10 | s3.2-access-review | `74741515` | `03_access_review.md` — 105 candidates reviewed against source |
| #1927 | UNT8-11 | s4.1-proposal | `963160a2` | `mapping_spec.json` `map-draft-1`, `04_proposal_review.md` |
| #1928 | UNT8-12 | s4.2-design-decisions | `4a91e1dd` | `design_decisions.json`, `map-v1`, `05_decisions.md` §1–§5 |
| #1929 | UNT8-13 | s4.3-known-incompat | `218dc441` | `05_decisions.md` §3b, 16 note decisions, `map-v1.1` |
| #1933 | UNT8-14 | s4.4-units | `170f7fc9` | `04_units.md`, `ops/u*.json` (Tier-4 ops), one-wave proposal |
| #1934 | UNT8-16 | s5.1.b01 (`w1-b0-reference`) | `d6fbff71` | u00 → `codes`/`plans`/`tenants`, live recon PASS |
| #1935 | UNT8-17 | s5.1.b02 (`w1-b1-detached-depth0`) | `11ef9735` | u06/u07/u08/u09, live recon PASS/PASS/**UNVERIFIED**/PASS, merged under `d-unverified-batch-merge` (§4) |
| #1936 | UNT8-24 | s5.1.b03 (`w1-b2-tenant-children-depth1`) | `481a730d` | u01/u02/u05, live recon PASS ×3 |
| #1937 | UNT8-23 | s5.1.b04 (`w1-b3-rating-invoicing-depth2`) | `7e66c71a` | u03/u04, live recon PASS ×2 |
| #1938 | UNT8-19 | s6.1-unverified-and-blind-spots | `1c095f45` | `05_decisions.md` §4b / §5b |
| #1940 | UNT8-20 | s6.2-prior-run-diff | `a1611288` | `06_prior_run_diff.md` |

20 PRs merged into the run branch plus one direct push; the first-parent log between `32baffd8` and `a1611288` holds exactly these 21 commits and nothing else. Steps without a PR into the run branch: s1.0-run-branch (UNT8-1: branch cut, plugin pin, harness install), s5.1.0-preflight (UNT8-15: wave-1 spec validated, `manifest_sha 55e68257b3f9` stamped on every batch result), s5.1.verify (UNT8-18: evidence on `origin/recon/wave-1-UNT8-18` @ `95720bb3`, four commits off `7e66c71a`, §4). The PR numbers not listed (#1918, #1920, #1926, #1930–#1932, #1939) are not on the run branch's first-parent history and are not part of this run's record.

## 3. Wave-1 verdict

**Wave verdict: PASS** — the worker batch results on the run branch and the independent verifier agree (`wave_verdict: "PASS"` in `origin/recon/wave-1-UNT8-18:.migration/recon/wave-1/wave-1-verify.json`; `unit_verdicts` PASS for all four batches; Tier-4 replay 27/27 ops matched). Every unit recon ran `--mode live` against the Oracle fixture and `mmp_rt_b4_oracle` under `map-v1.1` / `tol-1`.

| batch | units | worker `status` (run branch) | verifier re-run | worker `result.json` (run branch `a1611288`) | verifier `result.json` (`origin/recon/wave-1-UNT8-18` @ `95720bb3`, `git show` only) |
|---|---|---|---|---|---|
| `w1-b0-reference` | u00-reference (`codes`, `plans`, `tenants`) | PASS ([`recon/w1-b0-reference.json`](recon/w1-b0-reference.json)) | PASS | [`recon/u00-reference/result.json`](recon/u00-reference/result.json) | `.migration/recon/wave-1/w1-b0-reference/u00-reference/result.json` |
| `w1-b1-detached-depth0` | u06-audit-log, u07-customer-master, u08-customer-master-hist, u09-custbill-invoices | PASS on u06/u07/u09, **u08 UNVERIFIED** ([`recon/w1-b1-detached-depth0.json`](recon/w1-b1-detached-depth0.json): `recon_verdict_worst: "UNVERIFIED"`, `merge_eligible_units` = u06, u07, u09) | PASS on u06/u07/u09, u08 **UNVERIFIED** | [`u06`](recon/u06-audit-log/result.json), [`u07`](recon/u07-customer-master/result.json), [`u08`](recon/u08-customer-master-hist/result.json), [`u09`](recon/u09-custbill-invoices/result.json) | `.migration/recon/wave-1/w1-b1-detached-depth0/{u06-audit-log,u07-customer-master,u08-customer-master-hist,u09-custbill-invoices}/result.json` |
| `w1-b2-tenant-children-depth1` | u01-subscriptions, u02-usage-events, u05-notifications | PASS ([`recon/w1-b2-tenant-children-depth1.json`](recon/w1-b2-tenant-children-depth1.json)) | PASS | [`u01`](recon/u01-subscriptions/result.json), [`u02`](recon/u02-usage-events/result.json), [`u05`](recon/u05-notifications/result.json) | `.migration/recon/wave-1/w1-b2-tenant-children-depth1/{u01-subscriptions,u02-usage-events,u05-notifications}/result.json` |
| `w1-b3-rating-invoicing-depth2` | u03-rating, u04-invoices | PASS ([`recon/w1-b3-rating-invoicing-depth2.json`](recon/w1-b3-rating-invoicing-depth2.json)) | PASS | [`u03`](recon/u03-rating/result.json), [`u04`](recon/u04-invoices/result.json) | `.migration/recon/wave-1/w1-b3-rating-invoicing-depth2/{u03-rating,u04-invoices}/result.json` |

**`w1-b1-detached-depth0`, said plainly.** The batch PR #1935 merged with three live-PASS units and one UNVERIFIED unit under plan decision `d-unverified-batch-merge` — a manager decision, not a grader verdict. The pinned grader (`skills/wave-preflight/preflight.py` at `353280fc`) grades this batch **FAIL / `failure_class: insufficient_evidence`**, because `harness_evidence` takes the first non-PASS verdict (`UNVERIFIED`) and `gate_evidence_ok` admits only `PASS`; the verifier records the same hole on its side (no grader-clean verdict exists for a batch holding a by-design-empty unit — `verify-report.md` findings 1 and 11, `05_decisions.md` §5b P6). The run-branch batch JSON keeps the worker `status: PASS` with its `status_basis` spelled out. Nothing was seeded around the empty table and no verdict text was edited.

**UNVERIFIED count: 1** — `u08-customer-master-hist` (`customerMasterHist` ← `CUSTOMER_MASTER_HIST`, 0 source rows / 0 target documents, collection created empty with index `custId_1__id_1`; Tier 3 ran 0 checks, `merge_eligible: false` in both the worker and the verifier `result.json`). Why it is empty and what it leaves untested (163 mapped fields) is in `05_decisions.md` §4b. No other unit or root graded UNVERIFIED; embedded children (`invoices.lines` 29, `invoices.dunningAttempts` 5, `tenants.creditNotes` 5, `customerMaster.attributes` 70) were graded.

Verifier evidence lives on **`recon/wave-1-UNT8-18`** (not `recon/wave-1`) by plan decision `d-verify-branch-collision`: `origin/recon/wave-1` already held another run's wave-1 evidence (`36873379`, manifest `b11c0e7b2f31`), and the pinned `preflight.py --verify` hard-codes the `recon/wave-1` name, so it reports this run's verifier paths as "not committed" (P5, verify-report finding 12). The branch was never merged into or checked out on the run branch (`git merge-base --is-ancestor 95720bb3 origin/tp-run/mongodb-20261007T161014Z` → false). Independence caveat: the verifier ran on the same fixture host as the batch worker (P10, verify-report finding 7).

## 4. Final Atlas footprint of `mmp_rt_b4_oracle` (`dbStats`, read-only)

Two readings, both well under the 10 MB budget. No connection was opened by this report; both are pasted from the artifacts named.

| reading | when (UTC) | collections | objects | avgObjSize | dataSize | storageSize | indexes | indexSize | source |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| (a) verifier, driver `dbStats` | 2026-10-07 ≈20:19 (re-runs generated 20:17:23–20:19:00) | 16 (views 0) | 2,980 | 590.88 B | 1,760,835 B | 1,716,224 B | 42 | 1,105,920 B | `origin/recon/wave-1-UNT8-18:.migration/recon/wave-1/wave-1-verify.json` → `dbStats`; `verify-report.md` "dbStats" |
| (a′) verifier, `mongosh` paste | same session | 16 | 2,980 | — | 1,760,835 B | 1,716,224 B | 42 | 1,122,304 B | `origin/recon/wave-1-UNT8-18:.migration/recon/wave-1/probes/dbstats_mongosh.txt` |
| (b) final fixture-host `mongosh`, `MONGODB_ATLAS_URI` by name | 2026-10-07T20:46:49Z | 16 (views 0) | 2,980 | 590.88 B | 1,760,835 B | 1,716,224 B | 42 | 1,269,760 B | pasted by the fixture host into the manager's close-out inputs (ticket UNT8-21); not committed as a file |

Objects, `dataSize` and `storageSize` are identical across all three; only `indexSize` moves (1,105,920 → 1,122,304 → 1,269,760 B). With no change in objects or data, that is WiredTiger index-file growth (checkpoint/page allocation on the 42 index files), not new data. **Total data + index at the last reading: 1,760,835 + 1,269,760 = 3,030,595 B ≈ 3.03 MB; storage + index 2,985,984 B ≈ 2.99 MB — under 3.1 MB, well under 10 MB.** The 16 collections are the 15 mapped roots (`billingAuditLog`, `codes`, `customerMaster`, `customerMasterHist`, `invoiceHeader`, `invoiceLine`, `invoices`, `notifications`, `plans`, `ratingPeriods`, `ratingResults`, `subscriptions`, `subscriptionsHist`, `tenants`, `usageEvents`) plus the empty `_connectivity_probe` left by the UNT8-4 round-trip (P11, verify-report finding 9). Root counts source = target on every collection (verify-report "Root counts": 73/32/201/0/1000/1500/9/2/3/8/8/20/6/15/103).

## 5. Diff against the prior record F1–F82 ([`06_prior_run_diff.md`](06_prior_run_diff.md))

| class | count |
|---|---:|
| fixed | **30** |
| still present | **27** |
| newly regressed | **0** |
| not exercised | **25** |

82 rows (80 distinct findings; F10 and F80 are duplicates), counts verified by the script in `06_prior_run_diff.md` §4. **40 findings of this run have no F1–F82 counterpart** (`06_prior_run_diff.md` §3). 11 of the 30 "fixed" rows are fixed on the main path only and leave a residual recorded as a §5b item; 17 of the 25 "not exercised" rows are harness/merge-contract paths this run avoided by design. One post-diff note was appended at the end of `05_decisions.md` (two wording corrections of record; no §5b item found wrong).

## 6. Stop point

**Stopped after the verified wave; no parallel-run, no cutover, no repointing of billing-service or golden-app code; Oracle container and Atlas database left in place for the requester to clean up.**

Concretely, not done by this run: no coexistence period or scheduled recon cycles; no delta sync / CDC from Oracle (the target is a point-in-time copy of the fixture as seeded and exercised); no cutover rehearsal, authorization or principal; `services/legacy-billing` and every consumer still read Oracle and no golden-app code was changed to use `mmp_rt_b4_oracle`; no rollback owner (nothing to roll back); no plugin fix (every defect in `05_decisions.md` §5b is recorded with `file:line` at `353280fc` and left in place); no teardown (§10). The plugin-validation deliverable is the findings record, not the migrated data.

## 7. Push hygiene — nothing of this run reached the plugin repo, `tech-partnerships` or `main`

Checked for this report with `git ls-remote` (2026-10-07 ≈21:10Z) and `git merge-base --is-ancestor` over every first-parent commit of the run:

| remote ref | tip | check |
|---|---|---|
| `mongo-migration-plugin` `HEAD` / `refs/heads/main` | `353280fc837193a40ccc005cb62fb4ffaf8ac16f` | identical to the pin; newest commit on any plugin branch is `353280fc` itself (2026-10-07T14:57:49Z, before this run began at 16:10Z); no plugin branch holds a commit dated after 16:00Z — **nothing pushed** |
| `otterworks` `refs/heads/tech-partnerships` | `32baffd8674ec0198f632cadda40fc40eeacdd8a` | unchanged since 2026-09-27 (the run branch's base); contains none of the 21 run commits |
| `otterworks` `refs/heads/main` | `af476560b77d23cdc613b08332125250bbb5396a` | last merge 2026-10-07T03:06Z (#1829, before the run); contains none of the 21 run commits |
| `otterworks` `refs/heads/tech-partnerships-solutions` | `07d4e82f48062596255a197ebabdf72ee187ad54` | 2026-08-16, untouched and never consulted |

Branches this run pushed to `otterworks`: `tp-run/mongodb-20261007T161014Z` (the record), `recon/wave-1-UNT8-18` (verifier evidence, `95720bb3`, must stay on origin for §3's paths to resolve), the per-PR feature branches named in §2, and this report's branch.

## 8. Artifacts of the run (paths relative to `.migration/`)

| phase | artifact |
|---|---|
| scope | [`allowed_targets.json`](allowed_targets.json), [`authorizations.json`](authorizations.json) (`[]`), [`connectivity.json`](connectivity.json), [`recon_tolerances.json`](recon_tolerances.json) |
| fixture | [`fixtures/mmprt-mini.json`](fixtures/mmprt-mini.json); repo `testdata/legacy/mmp_rt_mini_seed.py`, `testdata/legacy/mmp_rt_exercise.sql` |
| assessment | [`census.json`](census.json), [`census_ddl.json`](census_ddl.json), [`census_diff.json`](census_diff.json), [`01_census_crosscheck.md`](01_census_crosscheck.md), [`data_profile.json`](data_profile.json), [`02_profile_gaps.md`](02_profile_gaps.md), [`02_dependency_register.md`](02_dependency_register.md), [`access_patterns.json`](access_patterns.json), [`03_access_scan_notes.md`](03_access_scan_notes.md), [`03_access_review.md`](03_access_review.md) |
| model | [`mapping_spec.json`](mapping_spec.json) (`map-v1.1`), [`design_decisions.json`](design_decisions.json), [`04_proposal_review.md`](04_proposal_review.md), [`05_decisions.md`](05_decisions.md) |
| units / wave | [`04_units.md`](04_units.md), [`ops/`](ops/) (Tier-4 ops `u*.json`) |
| per-unit recon (10) | [`recon/<unit>/`](recon/) `result.json`, `report.md`, `recon.summary.md` |
| per-batch | [`recon/w1-b0-reference.json`](recon/w1-b0-reference.json), [`recon/w1-b1-detached-depth0.json`](recon/w1-b1-detached-depth0.json), [`recon/w1-b2-tenant-children-depth1.json`](recon/w1-b2-tenant-children-depth1.json), [`recon/w1-b3-rating-invoicing-depth2.json`](recon/w1-b3-rating-invoicing-depth2.json) |
| verifier (other branch) | `origin/recon/wave-1-UNT8-18:.migration/recon/wave-1/{verify-report.md, wave-1-verify.json, probes/*, <batch>/<unit>/result.json}` |
| record | [`05_decisions.md`](05_decisions.md), [`06_prior_run_diff.md`](06_prior_run_diff.md), this file |

## 9. `05_decisions.md` — section index

- [§1 Proposer decision, rule and rationale — horror tables and history tables](05_decisions.md#1-proposer-decision-rule-and-rationale--horror-tables-and-history-tables)
- [§2 Manual corrections](05_decisions.md#2-manual-corrections-decision-id--what-changed--why-the-proposers-output-was-indefensible--evidence)
- [§3 Every proposer-raised open question and how it was resolved](05_decisions.md#3-every-proposer-raised-open-question-and-how-it-was-resolved) — [§3.1 `open_questions` (42)](05_decisions.md#31-collection-open_questions-42), [§3.2 `modeling.unresolved` (24) + 1](05_decisions.md#32-modelingunresolved-24-and-items-raised-by-the-patch-itself-1)
- [§3b Known incompatibilities (s4.3)](05_decisions.md#3b-known-incompatibilities-s43-known-incompat-unt8-13--every-row-of-profilesoraclemd--known_incompatibilities) — [§3b.1](05_decisions.md#3b1-the-five-retired-sequences-row-2), [§3b.2](05_decisions.md#3b2-embed-element-keys-sort-deterministically-row-10), [§3b.3 version bump to `map-v1.1`](05_decisions.md#3b3-how-the-notes-were-applied--version-bump-to-map-v11)
- [§4 Plan defaults as applied](05_decisions.md#4-plan-defaults-as-applied)
- [§4b UNVERIFIED units — wave 1 as graded](05_decisions.md#4b-unverified-units--wave-1-as-graded-s61-unverified-and-blind-spots-unt8-19)
- [§5 Proposer blind spots and input findings](05_decisions.md#5-proposer-blind-spots-and-input-findings-from-the-access-review-and-this-correction-work)
- [§5b Plugin tool wrong or blind — consolidated](05_decisions.md#5b-plugin-tool-wrong-or-blind--consolidated-s61-unverified-and-blind-spots-unt8-19) — [P](05_decisions.md#5b1-process-guard-and-preflight-p), [C](05_decisions.md#5b2-census-01_census_crosscheckmd-c), [G](05_decisions.md#5b3-data-profile-02_profile_gapsmd-173-stats-all-ok-none-skippedfailed-g), [A](05_decisions.md#5b4-access-scan-03_access_scan_notesmd-8-106-03_access_reviewmd-3-a), [M](05_decisions.md#5b5-proposer-and-modeling-04_proposal_reviewmd-9-2-corrections-3b-m), [H](05_decisions.md#5b6-harness-loader-and-profile-feedback-from-the-batch-prs-h), [§5b.7 Not tested by this run](05_decisions.md#5b7-not-tested-by-this-run)
- [§6 Pre-PR self-check](05_decisions.md#6-pre-pr-self-check-agentsskillstp-pre-pr-self-check) — [§6.1 (s4.3)](05_decisions.md#61-pre-pr-self-check-for-s43-known-incompat-unt8-13-map-v11), [§6.2 (s6.1)](05_decisions.md#62-pre-pr-self-check-for-s61-unverified-and-blind-spots-unt8-19-4b5b)
- [Post-diff note — 2026-10-07](05_decisions.md#post-diff-note--2026-10-07-after-reading-the-prior-record-ticket-diff-this-run-against-the-prior-record)

`06_prior_run_diff.md`: [§0 classification rule](06_prior_run_diff.md#0-how-each-row-was-classified) · [§1 F1–F82](06_prior_run_diff.md#1-f1f82) · [§2 class counts](06_prior_run_diff.md#2-class-counts) · [§3 new in this run](06_prior_run_diff.md#3-new-in-this-run--2--5b-items-with-no-f1f82-counterpart) · [§4 self-check](06_prior_run_diff.md#4-self-check-of-this-file).

## 10. Hand-back and cleanup (listed, not executed)

Both the Oracle fixture container and the Atlas database are **left in place**. Nothing below was run; this run performed no drops anywhere.

1. **Oracle Free fixture** — lives only on the fixture host that seeded it and is not reachable from this report's session. There: `make -C ~/repos/otterworks oracle-billing-down` (compose project `otterworks-oracle-billing`, `down -v` removes the `mmprt` seed with the volume). Re-creating it is PR #1914's recipe.
2. **Atlas database `mmp_rt_b4_oracle`** (≈3 MB, §4) — when the record is no longer needed, a human with the Atlas credentials drops exactly this database and nothing else; every other database on the cluster belongs to another run and is out of this run's scope.
3. **Branches** — `tp-run/mongodb-20261007T161014Z` is the record and stays; `recon/wave-1-UNT8-18` must stay on origin for the verifier paths in §3 to resolve.
4. **Per-VM state** — `~/mmp` clones and the harness venvs hold no run state and may be deleted freely.

## 11. Self-check for this PR (`.agents/skills/tp-pre-pr-self-check`)

Writes only `.migration/RUN_REPORT.md`; no code, spec, tolerances, recon artifact or `05_decisions.md` touched. No Oracle or Atlas connection opened (footprint pasted from §4's named sources). Secrets referenced by name only; no user-identifying information. Every sha in §2 re-read from `git log --first-parent`; both sha256 pins recomputed; §7 from `git ls-remote` + `merge-base`. `make tp-smoke` green (after `mise trust`). Unverified paths of this report: reading (b) of §4 is a paste relayed by the fixture host and is not reproducible from the repo; the Oracle container's current state was not observed from this session. Items of the checklist that concern unit code (NULL attribution, namespace prefixes, DDL, idempotency rerun, `*.recon.json`) do not apply to a prose-only PR and are listed here as not applicable rather than green.
