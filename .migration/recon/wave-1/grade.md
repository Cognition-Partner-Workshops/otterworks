# Wave 1 — grading record (s4.1.c, UNT7-16)

Run branch `tp-run/mongodb-20261007T062215Z` at `7b20d7ad` (everything already merged: #1862–#1866 batches, #1867 verify, #1868 recon refresh, #1869 verifier re-stamp). This is the grading **record**; no merge was performed by this step. Wave pin `map-draft-4` (`f5f8df83…`), tolerances `1`, `manifest_sha b11c0e7b2f31`, `auto_merge false`. Plugin clone HEAD `6bae4f891953ec0822a5fb30707087a718e9df01`, branch tip `ada6699d…`. Machine-readable twin: `grade.json`.

```
GIT_DIR=<repo>/.git python3 <plugin>/skills/wave-preflight/preflight.py --wave <repo>/.migration/waves/wave-1.json --root <repo> \
  --grade <repo>/.migration/recon/w1-b0{1..5}.batch.json \
  --verify <repo>/.migration/recon/wave-1/verify-result.json --run-id ticket-cf5c46af9c3345b98534ff860bb73f38 [--merged merged.json]
```
(run from `$HOME`, F4/F63; without `GIT_DIR` the grader's plain `git fetch origin …` fails.)

## 1. Graded batches (`--grade` ×5 `--verify`, exit 0)

| batch | status | failure_class | merge_eligible | harness_merge_eligible | recon | PR | evidence branch |
|---|---|---|---|---|---|---|---|
| w1-b01 | PASS | — | True | True | PASS live/migration_cluster | 1862 | `devin/1791370818-w1-recon-refresh` |
| w1-b02 | PASS | — | True | True | PASS live/migration_cluster | 1863 | `devin/1791370818-w1-recon-refresh` |
| w1-b03 | PASS | — | False | False | PASS live/migration_cluster | 1864 | `devin/1791370818-w1-recon-refresh` |
| w1-b04 | PASS | — | True | True | PASS live/migration_cluster | 1865 | `devin/1791367911-w1-b04-load` |
| w1-b05 | PASS | — | True | True | PASS live/migration_cluster | 1866 | `devin/1791368621-w1-b05-load` |

`verify_problems: []`; verifier `wave_verdict PASS`, `unit_verdicts` PASS for all five (re-stamped by UNT7-26 from `verifier_batch_verdicts`, F80).

**`mergeable_prs`:** #1862, #1863, #1865, #1866.

## 2. Merged check (`--merged`)

| merged.json | exit | verify_problems |
|---|---|---|
| actually merged set #1862–#1869 | 1 | `merged_prs includes unverified` #1864, #1867, #1868, #1869 |
| mergeable set only #1862, #1863, #1865, #1866 | 0 | none |

- **#1864 (w1-b03)** was merged on the manager's decision `d-orphan-grading = child-where` although never in `mergeable_prs` (invoiceHeader `merge_eligible false`, F72). The grader flags it; it has no field for a decision-merged PR — **F81**, recorded, not reverted.
- **#1867 / #1868 / #1869** are the verifier, the recon refresh and the verifier re-stamp — not batch PRs. `validate_merge` accepts exactly the mergeable URLs and nothing else, so every evidence PR that lands on the run branch reads as `unverified` — **F82**.

## 3. Downgrades and caveats carried into the wave

- **invoiceHeader (w1-b03) — PASS, not merge-eligible (F72).** Harness PASS (Tier 1 3 / Tier 2 2 / Tier 3 2,463 checks, 0 findings) with the warning `embed invoiceHeader.lines: scoped by a where-predicate; extra target elements not checked`; `report.py` never grants `merge_eligible` to a unit with a warning. Graded `INVOICE_LINE` scope is 1,463 of 1,500 (`child_where`, F71). The 37 ghost lines live in `mmp_rt_b3_oracle.invoice_lines_orphaned` (`orphan: true`, raw `invoiceId`); hand proof **1463 + 37 = 1500** on target and owner side, 0 orphan invoiceIds resolve to a header, 0 lineId on both sides (`w1-b03.evidence.json`), re-proved by the verifier (`verify-report.md` §4.1).
- **UNVERIFIED on 0 rows (F70):** `billingAuditLog` (source 0 rows; target collection never created); `customerMasterHist` (source 0 rows; empty collection + index only); `subscriptionsHist` (source 0 rows; TRG_SUBSCRIPTIONS_HIST never fired in the fixture (F73); latent `histDt` format defect unexercised, F73). Their PASS verifies nothing.
- **`connectivity.json` `blocked: true`** (`d-target-principal`, F12–F13): the target principal probe stays BLOCKED for privilege excess; loads ran under `MONGODB_ATLAS_URI` with the `mongo_guard` database allowlist as the only scope control. File unchanged all run.
- **Evidence-branch dependency (F79):** `w1-b01/02/03.batch.json` cite `branch: devin/1791370818-w1-recon-refresh`; the grader reads their `recon_results` from `origin/<branch>`, so the b01–b03 PASS depends on that branch staying on origin (manager keeps it for the run; nothing pins its SHA).
- **Verifier file re-stamped (F78/F80):** `unit_verdicts` widened from {b04, b05} to all five after the refresh, from the verifier's own `verifier_batch_verdicts`; no new recon.

## 4. Atlas footprint (read-only)

`mmp_rt_b3_oracle` `dbStats`: 16 collections / 1,423 objects / dataSize 1,458,565 B / storageSize 2,064,384 B / 37 indexes (indexSize 1,523,712 B); budget 10 MB. Identical to the s4.1.r before/after snapshot.

Collection counts: codes 32, creditNotes 5, customerMaster 201, customerMasterHist 0, dunningAttempts 1, invoiceHeader 1000, invoice_lines_orphaned 37, invoices 4, notifications 1, plans 3, ratingPeriods 3, ratingResults 3, subscriptions 15, subscriptionsHist 0, tenants 15, usageEvents 103.

`listDatabases` (names only): `admin`, `local`, `mmp_rt_b1_mysql`, `mmp_rt_b1_tsql`, `mmp_rt_b2_tsql`, `mmp_rt_b3_oracle`, `ow_billing_migration`, `ow_tp_billing_20261001T233613Z`, `ow_tp_mmp_live`. The only database this run wrote is `mmp_rt_b3_oracle`; the other `mmp_rt_*` / `ow_*` names belong to other runs and already appear in `.migration/recon/w1-b01.evidence.json` before the first wave-1 write — **no other database was created by this run**.

## 5. Edits

Only `recon/wave-1/grade.md`, `recon/wave-1/grade.json`, `05_decisions.md` (F81–F82) and the README grade section. `connectivity.json`, `mapping_spec.json`, `waves/`, tolerances, batch JSONs and the verifier's files are untouched.
