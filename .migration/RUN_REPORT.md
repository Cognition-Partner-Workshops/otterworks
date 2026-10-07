# Run report — `mmp_rt_b3_oracle` (close-out, plan step `s7.2-run-report`, UNT7-18)

Hand-back of the unattended red-team run of the `mongo-migration` Devin plugin against the OtterWorks legacy Oracle billing estate (`services/legacy-billing/db/oracle/**`, schema `OW_BILLING`). This is the last ticket of the run: it reports, it tears nothing down, and it executes nothing against the source or the target beyond the read-only Atlas footprint check in §6. Every number below is read from an artifact already merged on the run branch, except §6, which was recomputed live in this session. The main output of the run is the findings record `05_decisions.md` (§8); this file is the index that points at it.

## 1. Identity

| item | value |
|---|---|
| run branch | `tp-run/mongodb-20261007T062215Z` on `Cognition-Partner-Workshops/otterworks`, tip at report time `1837818f` (#1871 merged); this report is the next and final PR |
| plugin under test | `Cognition-Partner-Workshops/mongo-migration-plugin` branch `devin/1791335937-app-aware-modeling-next`, tip `ada6699dbbc0112288884a050766ef1332da7ac1`, plus `git cherry-pick 865b105d695090615d1efa908fd9621e7bbd7bff` (PR #54, recon `index_keys` fix; `git patch-id --stable` `e102025d`); tree `6f1b121812e3de4c60ddabd203878c7bc4f06fe6` |
| plugin clone HEAD (this session) | `550bec533d4c32567de4b1b8308e31124eb24314` (fresh clone + cherry-pick; tree `6f1b1218…` as pinned). The post-cherry-pick commit id differs per clone (F6); earlier clone HEADs are listed in `05_decisions.md` F6 and §0. Never pushed to. |
| recon harness | `/home/ubuntu/.venvs/recon`, installed editable from the clone (F1), `recon selftest` PASS, PyYAML installed by hand (F3) |
| source | local Oracle Free fixture (per-VM), container `otterworks-oracle-billing-oracle-billing-1`, host port 52521, PDB `FREEPDB1`, schema `OW_BILLING`, principal `OW_BILLING_RO`, DSN in local env var `MMP_RT_SRC_DSN`, query concurrency 1 |
| target | shared Atlas M0 via secret `MONGODB_ATLAS_URI` (name only); database `mmp_rt_b3_oracle` only; budget 10 MB; nothing dropped at any point |
| mapping pin | `map-draft-4`, sha256 `f5f8df83ed10647698a6451bb195ad44a20aa3d80dd01cb99058ab51ee5ba763` |
| tolerances pin | `recon_tolerances.json` version `1`, sha256 `1a8ebb6c4c572bdfae68eb424d68007ef89416cd8d96eef0d504054fe70e0c01` (`d-tolerances: strict`) |
| wave manifest | `waves/wave-1.json`, `manifest_sha b11c0e7b2f31`, `source_access live`, `target_access migration_cluster`, `auto_merge false` |
| guard posture | F4 in force for the whole run: every command run from `$HOME` via `make -C` / `git -C` / absolute paths; `MONGO_GUARD_BASE_REF=origin/tp-run/mongodb-20261007T062215Z` exported after #1851 |

## 2. Merged PRs on the run branch (in merge order)

| PR | ticket | plan step | what landed | findings |
|---|---|---|---|---|
| #1849 | UNT7-1 | s1.1-toolchain | `.migration/README.md`, `05_decisions.md` scaffold, harness install | F1–F4 |
| #1850 | UNT7-5 | s1.5-tolerances | `recon_tolerances.json` v1 (strict) | F5–F6 |
| #1851 | UNT7-3 | s1.3-allowlist | `allowed_targets.json` (write scope `mmp_rt_b3_oracle`), guard demo | F7–F10 |
| #1852 | UNT7-2 | s1.2-fixture | Oracle mini seed `mmprt`, ro user, `fixture_counts.json` | F11 (+F6) |
| #1853 | UNT7-4 | s1.4-connectivity | `connectivity.json` (online; target BLOCKED `privilege_excess`) — blocked record | F12–F13 |
| #1854 | UNT7-6 | s2.1-census | `census.json`, `census_ddl.json`, `census_diff.json`, `census_dispositions.json` | F14–F17 |
| #1855 | UNT7-7 | s2.5-data-profile | `data_profile.json` (136 stats), `data_profile_handcheck.json` | F18–F23 |
| #1856 | UNT7-8 | s2.4-fixture | `fixtures/mmp-rt-mini.json` fixture manifest | F24–F25 |
| #1857 | UNT7-9 | s2.2-access-patterns | `access_patterns.json` (100 candidates), `dependency_register.json` | F26–F36 |
| #1858 | UNT7-10 | s2.2b-review-patterns | review: 62 confirmed / 38 rejected / 2 added; register corrections | F37–F40 |
| #1859 | UNT7-11 | s3.1-model-proposal | `mapping_spec.json` `map-draft-1`, `model_proposal_triage.json` | F41–F45 |
| #1860 | UNT7-12 | s3.2-design-review | `design_decisions.json` (82 decisions), `map-draft-2` | F46–F56 |
| #1861 | UNT7-13 | s4.0-derive-units | `units.json` (16 units), `waves/wave-1.json` (5 batches) | F57–F59 |
| #1862 | UNT7-14 + UNT7-23 | s4.1.b01 + s3.3 | batch b01 load + live recon; `map-draft-3` spec correction (two hand edits) | F60–F66 |
| #1863 | UNT7-19 | s4.1.b02 | batch b02 load + live recon | F67–F68 |
| #1864 | UNT7-20 + UNT7-24 | s4.1.b03 + s3.4 | batch b03 load + live recon; `map-draft-4` (`child_where`), orphan sink; merged on decision `d-orphan-grading` | F69–F72 |
| #1865 | UNT7-21 | s4.1.b04 | batch b04 load + live recon | F73 |
| #1866 | UNT7-22 | s4.1.b05 | batch b05 load + live recon (wave 1 complete) | F74 |
| #1867 | UNT7-15 | s4.1.v | independent verifier: `recon/wave-1/verify-report.md`, `verify-result.json`, 16 re-run artifact sets | F75–F77 |
| #1868 | UNT7-25 | s4.1.r | recon refresh of b01–b03 artifacts under the `map-draft-4` pin (recon-only, no reload) | F78–F79 |
| #1869 | UNT7-26 | s4.1.v2 | verifier re-stamp of `unit_verdicts` to all five batches | F80 (→F78) |
| #1870 | UNT7-16 | s4.1.c | grading record `recon/wave-1/grade.{md,json}` | F81–F82 |
| #1871 | UNT7-17 | s7.1-decisions-record | `05_decisions.md` consolidated (§0–§3) | — |

23 PRs, all merged into the run branch, none into `tech-partnerships`, `tech-partnerships-solutions` or `main`. The batch evidence of b01–b03 is read by the grader from `origin/devin/1791370818-w1-recon-refresh` (F79), so that branch must stay on origin for `preflight.py --grade` to reproduce §5.

## 3. Fixture actually seeded (source row counts)

Oracle Free (`container-registry.oracle.com/database/free:latest`, banner `Oracle AI Database 26ai Free Release 23.26.3.0.0`), seeded once at **mini** scale by `testdata/legacy/mmp_rt_mini_seed.py` under namespace `mmprt` (`seed 2443531857`, `batch_no 14531857`; 200 customers / 1,500 invoice lines / 5 core tenants), on top of the static rows shipped by `schema/03_seed_static.sql`. Counted inside the container as the owner (`fixture_counts.json`, recorded 2026-10-07T06:45Z) and re-checked owner-side by every batch and by the verifier (`recon/wave-1/evidence/fixture_counts_check.json`). The stock `demo`/`full` seeder scales were not run.

| table | rows | of which `mmprt` namespace | note |
|---|---:|---:|---|
| BILLING_AUDIT_LOG | 0 | — | zero-row unit (F70) |
| CODES | 32 | — | static reference data |
| CREDIT_NOTES | 5 | 0 | |
| CUSTOMER_MASTER | 201 | 200 | 41 dirty `SIGNUP_DT` text dates; 1 static row `OW-ADMIN-0001` |
| CUSTOMER_MASTER_HIST | 0 | — | zero-row unit (F70) |
| DUNNING_ATTEMPTS | 1 | — | |
| ENTITY_ATTR_VALUE | 70 | 66 | EAV rows embedded into `customerMaster.attributes` |
| FIXTURE_META | 2 | — | excluded from the model (F45) |
| INVOICES | 4 | — | |
| INVOICE_HEADER | 1,000 | 1,000 | |
| INVOICE_LINE | 1,500 | 1,500 | 37 planted orphans (`MMPRT-GHOST-%`) |
| INVOICE_LINES | 4 | — | |
| NOTIFICATIONS | 1 | — | |
| PLANS | 3 | — | |
| RATING_PERIODS | 3 | 0 | |
| RATING_RESULTS | 3 | — | |
| SUBSCRIPTIONS | 15 | 5 | |
| SUBSCRIPTIONS_HIST | 0 | 0 | zero-row unit; trigger cascade never fired (F73) |
| TENANTS | 15 | 5 | 10 static tenants |
| USAGE_EVENTS | 103 | 90 | |

20 tables, 25 indexes, 5 sequences, 5 packages + 5 bodies, 7 triggers, 2 scheduler jobs (disabled). The read-only principal sees the tables and triggers but is blind to PL/SQL source, sequences and jobs through `ALL_*` (F11).

## 4. Artifacts produced (paths relative to `.migration/` unless stated)

| step | artifact |
|---|---|
| toolchain / index | `README.md` (per-step recipes and commands), `05_decisions.md` (findings record, §8), this file |
| scope | `allowed_targets.json`, `authorizations.json`, `connectivity.json` (unchanged since #1853, `blocked: true`), `recon_tolerances.json` |
| fixture | `fixture_counts.json`, `fixtures/mmp-rt-mini.json`; repo: `testdata/legacy/mmp_rt_mini_seed.py`, `testdata/legacy/mmp_rt_ro_user.sql`, `docker-compose.oracle-billing.yml` (pre-existing) |
| assessment | `census.json`, `census_ddl.json`, `census_diff.json`, `census_dispositions.json`, `data_profile.json`, `data_profile_handcheck.json`, `access_patterns.json`, `dependency_register.json` |
| model | `mapping_spec.json` (`map-draft-4`), `design_decisions.json` (87 decisions; #83–#84 `applied_by: manual`, replay stops at #84), `model_proposal_triage.json` |
| units / wave | `units.json` (16 units, depth 0–3), `waves/wave-1.json` (5 batches) |
| loader / wrapper (repo) | `services/legacy-billing/migration/mongodb/load_units.py`, `services/legacy-billing/migration/mongodb/recon_unit.sh` |
| per-unit recon (16) | `recon/<unit>/{result.json,report.md,recon.summary.md}` (live verdict, `map-draft-4`), `recon/<unit>/fixture/` (fixture-first dry run) |
| per-batch | `recon/w1-b0{1..5}.batch.json`, `recon/w1-b0{1..5}.evidence.json`, `recon/w1-b0{1,2,3}.batch.ed1747e90f6e.json` (pre-refresh), `recon/w1-refresh.evidence.json` |
| verifier | `recon/wave-1/verify-report.md`, `recon/wave-1/verify-result.json`, `recon/wave-1/evidence/{probes.json,probe.py,parity.json,parity.py,fixture_counts_check.json,target_before.json,target_after.json,target_snapshot_compare.json,preflight_verify.out}`, `recon/wave-1/w1-b0N/<unit>/` (16 independent artifact sets) |
| grade | `recon/wave-1/grade.md`, `recon/wave-1/grade.json` |

## 5. Wave 1 verdicts

**Graded (`preflight.py --grade` ×5 `--verify`, exit 0, `recon/wave-1/grade.json`):** 5/5 batches PASS.

| batch | units | status | merge_eligible | PR |
|---|---|---|---|---|
| w1-b01 | codes, tenants, plans, customerMaster, billingAuditLog | PASS | true | #1862 |
| w1-b02 | ratingPeriods, creditNotes, usageEvents, notifications, subscriptions | PASS | true | #1863 |
| w1-b03 | invoiceHeader, customerMasterHist (+ sink `invoice_lines_orphaned`) | PASS | **false** (F72: `invoiceHeader` scoped-embed warning) | #1864 (decision-merged, F81) |
| w1-b04 | invoices, subscriptionsHist, ratingResults | PASS | true | #1865 |
| w1-b05 | dunningAttempts | PASS | true | #1866 |

`mergeable_prs` = #1862, #1863, #1865, #1866 (four, not five). `--merged` with the real merged set #1862–#1869 exits 1 (`merged_prs includes unverified` #1864, #1867, #1868, #1869 — F81/F82); with the four mergeable PRs it exits 0. The grader has no field for a decision-merged batch PR or for evidence PRs.

**Verifier (`recon/wave-1/verify-report.md`, independent session, nothing loaded):** wave verdict **PASS**, 16/16 units live PASS under `map-draft-4`; probes and parity replays equal on both sides; target byte-identical before/after. Three units are **UNVERIFIED** because the harness graded 0 rows against 0 docs: `billingAuditLog` (target collection never created), `customerMasterHist` (empty collection + index only), `subscriptionsHist` (trigger cascade never fired in the fixture; latent `histDt` format defect F73 confirmed, not fixed). The 37-row orphan remainder is proved by hand only (`1,463 + 37 = 1,500`, 0 orphan `invoiceId` resolving to a header, 0 `lineId` on both sides), by the b03 evidence and again by the verifier.

**Gate `g-wave1-pass` is deliberately left unticked.** The harness verdicts above are PASS, but the merge contract (`--merged` exit 1 on the real set), the three UNVERIFIED units, the hand-only orphan proof and the blocked target principal (§7) are the evidence a human must weigh before ticking it; no worker claim does that.

## 6. Atlas footprint (read-only, recomputed in this session)

`listDatabases` over `MONGODB_ATLAS_URI` (names only): `admin`, `local`, `mmp_rt_b1_mysql`, `mmp_rt_b1_tsql`, `mmp_rt_b2_tsql`, `mmp_rt_b3_oracle`, `ow_billing_migration`, `ow_tp_billing_20261001T233613Z`, `ow_tp_mmp_live`. Identical to the list recorded in `recon/w1-b01.evidence.json` before the first wave-1 write and in `recon/wave-1/grade.md` §4: **the only database created or written by this run is `mmp_rt_b3_oracle`**; every other name belongs to another run and pre-dates this one.

`db.stats()` of `mmp_rt_b3_oracle`: **16 collections / 1,423 objects / dataSize 1,458,565 B / storageSize 2,064,384 B / 37 indexes (indexSize 1,523,712 B)** — well under the 10 MB budget and identical to the s4.1.r before/after snapshot and the grade record.

| collection | docs | | collection | docs |
|---|---:|---|---|---:|
| codes | 32 | | invoices | 4 |
| creditNotes | 5 | | notifications | 1 |
| customerMaster | 201 | | plans | 3 |
| customerMasterHist | 0 | | ratingPeriods | 3 |
| dunningAttempts | 1 | | ratingResults | 3 |
| invoiceHeader | 1,000 (1,463 embedded `lines`) | | subscriptions | 15 |
| invoice_lines_orphaned | 37 (F47 sink, not a spec collection) | | subscriptionsHist | 0 |
| | | | tenants | 15 |
| | | | usageEvents | 103 |

`billingAuditLog` is a unit of w1-b01 and a target in `allowed_targets.json`, but **the collection was never created**: the source table has 0 rows and the spec declares no index for it, so the loader had nothing to materialise (F68/F70). 16 collections on the target = 15 spec collections + the orphan sink. Nothing was written, dropped or indexed by this ticket.

## 7. Deliberately NOT done

- **Parallel-run**: no coexistence period, no scheduled recon cycles, no green-cycle count. Wave 1 was loaded once (reloads were `delete_many` + `insert_many` of the same data) and reconciled once live per unit.
- **Delta sync / CDC**: no change capture from Oracle, no watermark; the target is a point-in-time copy of the fixture as seeded.
- **Cutover**: no cutover rehearsal, no cutover authorization, no cutover principal.
- **Application repoint**: `services/legacy-billing` and every consumer still read Oracle; no application code was changed to use `mmp_rt_b3_oracle`; the trigger business rules and `computed` columns moved to "application layer" by decision have no implementation or test (§3 item 10 of `05_decisions.md`).
- **Rollback owner**: none named; nothing to roll back since nothing was repointed.
- **Target principal**: `connectivity.json` stays `blocked: true` (`target.reason: privilege_excess` — `MONGODB_ATLAS_URI` carries `readWriteAnyDatabase@admin` + `dbAdminAnyDatabase@admin`; decision `d-target-principal`). No database-scoped Atlas user was created and the policy never switched to `auto`; write scope was enforced by `load_units.py` / `recon_unit.sh` against `allowed_targets.json` and by `mongo_guard`, not by the principal (F12, F13, F58).
- **Wave gate `g-wave1-pass`**: not ticked (§5).
- **Plugin fixes**: every defect in F1–F82 is recorded with its `file:line` and left in place in the clone; the plugin repo was never pushed to.
- **Teardown**: nothing — see §9.

## 8. Findings record

`05_decisions.md`: **80 distinct findings in numbers F1–F82** (F10 folded into F6, F80 into F78) — 31 `wrong` · 42 `blind` · 7 `manual-correction`; by component: schema-modeling 42, mongo-recon-harness 12, wave-preflight 9, migration-planning 6, mongo-migration 3, run environment 2, hooks 2, run recipe 1, run 1, wave-planning 1, wave-verify 1. §1b lists the 9 hand steps that stand between the plugin's output and the merged artifacts; §2 maps the proposer's 24 `modeling.unresolved` items to their decisions; §3 lists the 11 things the wave-1 PASS does not attest. That file, not this report, is the deliverable of the red team.

## 9. Hand-back and cleanup (listed, not executed)

Both the fixture container and the Atlas database are **left in place** by this run. Nothing below was run; this run performed no drops anywhere.

1. **Oracle Free fixture (per-VM).** The container lives only on the VM(s) that seeded it; it is not reachable from this report's session. On such a VM, from `$HOME` (F4):
   ```sh
   make -C ~/repos/otterworks oracle-billing-down
   # equivalent: ORACLE_BILLING_DB_PORT=52521 docker compose -f ~/repos/otterworks/docker-compose.oracle-billing.yml -p otterworks-oracle-billing down -v
   ```
   `down -v` removes the container and its volume (the `mmprt` seed with it). The runtime manifest `testdata/legacy/manifests/mmprt.json` is gitignored and can be deleted with the container. Re-creating the fixture is the committed recipe in `README.md` ("Source fixture").
2. **Atlas database `mmp_rt_b3_oracle`** (shared M0, ≈2.06 MB storage). When the record is no longer needed, a human with the Atlas credentials drops exactly this database — e.g. `mongosh "$MONGODB_ATLAS_URI" --eval 'db.getSiblingDB("mmp_rt_b3_oracle").dropDatabase()'` — and nothing else: `ow_tp_*`, `ow_billing_*`, `mmp_rt_b1_*`, `mmp_rt_b2_*` belong to other runs. The 16 collections and 37 indexes are those in §6.
3. **Local venv** `/home/ubuntu/.venvs/recon` and the plugin clone (per-VM, no state of the run in them) may be deleted freely.
4. **Branches.** `tp-run/mongodb-20261007T062215Z` is the record and stays. The evidence branch `devin/1791370818-w1-recon-refresh` (and `devin/1791367911-w1-b04-load`, `devin/1791368621-w1-b05-load`) must stay on origin while `preflight.py --grade` is expected to reproduce §5 (F79); deleting them turns the b01–b05 grades into `insufficient_evidence`.

## 10. Self-check for this PR

Writes only `.migration/RUN_REPORT.md` and one index line in `.migration/README.md`; no code, no spec, no tolerances, no `connectivity.json`, no recon artifacts touched. Atlas: read-only (`listDatabases`, `dbStats`, `count_documents`), footprint identical before and after (§6). Oracle: not contacted. Secrets referenced by name only. `make tp-smoke` green from `$HOME` (`mise trust` first). Unverified paths: none introduced; the run's own are §5 and §7.
