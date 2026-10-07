run_id: ticket-cf5c46af9c3345b98534ff860bb73f38
manifest_sha: b11c0e7b2f31

# Wave 1 — independent verification (plan step `s4.1.v`)

Verifier session did not load any batch. Everything below was recomputed in this session from the committed spec against a freshly rebuilt fixture and the live target; nothing is copied from batch evidence.

## Identity

| item | value |
|---|---|
| run branch | `tp-run/mongodb-20261007T062215Z` @ `9b0c3e7a` (unchanged through the run; rebased before numbering findings) |
| report branch | `recon/wave-1` (off the run branch) |
| plugin | `Cognition-Partner-Workshops/mongo-migration-plugin` branch `devin/1791335937-app-aware-modeling-next` + `git cherry-pick 865b105d695090615d1efa908fd9621e7bbd7bff`; clone **HEAD `88dea6ae4f876e9d9fe7828bb8a24337c7873145`**, branch tip `ada6699dbbc0112288884a050766ef1332da7ac1` (post-cherry-pick SHA differs per clone, F6) |
| harness | `recon selftest` PASS; harness unit tests 196 passed; PyYAML installed by hand (F3) |
| mapping | `map-draft-4`, sha256 `f5f8df83ed10647698a6451bb195ad44a20aa3d80dd01cb99058ab51ee5ba763` (== wave pin) |
| tolerances | version `1`, sha256 `1a8ebb6c4c572bdfae68eb424d68007ef89416cd8d96eef0d504054fe70e0c01` (== wave pin) |
| wave manifest | `.migration/waves/wave-1.json`, `manifest_sha b11c0e7b2f31`, `source_access live`, `target_access migration_cluster`, `auto_merge false` |
| source | local Oracle Free fixture, `MMP_RT_SRC_DSN` (principal `OW_BILLING_RO`, `CURRENT_SCHEMA OW_BILLING`), `--source-concurrency 1`, `--seed 1` |
| target | Atlas database `mmp_rt_b3_oracle` only, `--target-class migration_cluster`, secret `MONGODB_ATLAS_URI` (name only); nothing written, nothing dropped |
| guard posture | F4 in force: every command run from `$HOME` via `make -C` / `git -C` / absolute paths; `MONGO_GUARD_BASE_REF=origin/tp-run/mongodb-20261007T062215Z` exported |
| redaction | `RECON_REDACT_SALT` unset → all 16 artifacts `redaction_salted: false` (F63b, unchanged) |

## Wave verdict

**PASS** — all five batches re-graded PASS by the harness under the pinned spec, every probe and parity replay equal on both sides. Qualifications the manager must carry into merge grading (not hidden in the PASS):

- **`preflight.py --grade` under manifest `b11c0e7b2f31` grades only w1-b04 and w1-b05 PASS.** w1-b01, w1-b02 and w1-b03 come back `FAIL / insufficient_evidence` ("PASS downgraded: … graded mapping map-draft-3 / tolerances 1; the ticket is map-draft-4 / 1"; b03 on `customerMasterHist`, never re-run after the s3.4 re-pin) — their batch results were produced under manifest `ed1747e90f6e` and were merged anyway. `verify-result.json` therefore keys `unit_verdicts` on w1-b04 and w1-b05 only, as the contract demands (exactly the graded PASS set), and carries the verifier's verdict for all five batches in `verifier_batch_verdicts`. The data is not in question — every unit of b01–b03 is PASS in this session's own live runs (§3); the batch *evidence* is stale (F76). Re-grading b01–b03 needs a re-run of their harness artifacts under `map-draft-4` on their branches or a manager decision; the verifier does not do either.

- `invoiceHeader` (w1-b03) is harness PASS but `merge_eligible: false` (F72, scoped embed warning); the hand proof in §4.1 is the only evidence for the 37-row remainder.
- `billingAuditLog`, `customerMasterHist`, `subscriptionsHist` are harness PASS on 0 rows and are **UNVERIFIED** (§4.9, F68/F70/F73) — the batch verdicts PASS because the harness says so, but these three units verified nothing.
- 11 of 16 committed batch artifacts cite a superseded mapping version (F76); verdicts do not change under `map-draft-4`.

| batch | units | verdict | basis |
|---|---|---|---|
| w1-b01 | codes, tenants, plans, customerMaster, billingAuditLog | **PASS** (verifier) / preflight grade of batch evidence: FAIL insufficient_evidence | 5/5 live PASS under map-draft-4 (batch artifacts cite map-draft-3, manifest ed1747e90f6e); billingAuditLog UNVERIFIED (0 rows, collection absent) |
| w1-b02 | ratingPeriods, creditNotes, usageEvents, notifications, subscriptions | **PASS** (verifier) / preflight grade of batch evidence: FAIL insufficient_evidence | 5/5 live PASS under map-draft-4 (batch artifacts cite map-draft-3, manifest ed1747e90f6e) |
| w1-b03 | invoiceHeader, customerMasterHist | **PASS** (verifier) / preflight grade of batch evidence: FAIL insufficient_evidence (customerMasterHist artifact map-draft-3) | 2/2 live PASS; invoiceHeader merge_eligible false (F72), orphan proof holds; customerMasterHist UNVERIFIED (0 rows) |
| w1-b04 | invoices, subscriptionsHist, ratingResults | **PASS** (verifier and preflight grade) | 3/3 live PASS; subscriptionsHist UNVERIFIED (0 rows, F73 latent defect confirmed) |
| w1-b05 | dunningAttempts | **PASS** (verifier and preflight grade) | 1/1 live PASS |

No batch is DRIFT-EXPLAINED: no live mismatch occurred, so the "re-run the source side twice" rule was never triggered (fixture is static; per-table counts matched `fixture_counts.json` before and the target was byte-identical in `dbStats` after).

## 1. Fixture rebuild (own VM)

`make -C ~/repos/otterworks oracle-billing-up` → container healthy; `DB_PORT=52521 uv run --no-project --with oracledb==2.5.1 python testdata/legacy/mmp_rt_mini_seed.py` (`ns=mmprt scale=mini seed=2443531857`); `testdata/legacy/mmp_rt_ro_user.sql` as `system` → `ow_billing_ro ready`. All 20 table counts in `.migration/fixture_counts.json` match exactly (`evidence/fixture_counts_check.json`, `match: true`): CUSTOMER_MASTER 201, INVOICE_HEADER 1000, INVOICE_LINE 1500 (37 orphans by `NOT EXISTS`, 37 `MMPRT-GHOST-%`), ENTITY_ATTR_VALUE 70, TENANTS 15, SUBSCRIPTIONS 15, USAGE_EVENTS 103, CODES 32, INVOICES 4, INVOICE_LINES 4, CREDIT_NOTES 5, RATING_PERIODS 3, RATING_RESULTS 3, PLANS 3, DUNNING_ATTEMPTS 1, NOTIFICATIONS 1, FIXTURE_META 2, BILLING_AUDIT_LOG 0, CUSTOMER_MASTER_HIST 0, SUBSCRIPTIONS_HIST 0.

## 2. Target before / after (names-only `listDatabases`, `dbStats`)

| | before `2026-10-07T10:37:04.502321Z` | after `2026-10-07T10:45:11.098829Z` |
|---|---|---|
| databases | 9: `admin, local, mmp_rt_b1_mysql, mmp_rt_b1_tsql, mmp_rt_b2_tsql, mmp_rt_b3_oracle, ow_billing_migration, ow_tp_billing_20261001T233613Z, ow_tp_mmp_live` | identical |
| `mmp_rt_b3_oracle` collections / objects / indexes | 16 / 1423 / 37 | 16 / 1423 / 37 |
| dataSize / storageSize / indexSize (B) | 1458565 / 2064384 / 1523712 | 1458565 / 2064384 / 1523712 |
| per-collection counts and index counts | 16 collections | identical (`evidence/target_snapshot_compare.json`: `diff_names_counts_indexes: {}`, `dbStats_diff: {}`) |

Nothing new appeared, nothing changed; storage 2.064 MB < 10 MB. (The ticket quoted storageSize 2,048,000 B; the server reports 2064384 B both before and after — WiredTiger allocation, not data.)

## 3. Harness re-run — one `live` run per unit, all 16 units, pinned spec

Command per unit (from `$HOME`): `~/repos/otterworks/services/legacy-billing/migration/mongodb/recon_unit.sh <unit> live --out .migration/recon/wave-1/<batch>/<unit>` → `recon run --family oracle --mapping .migration/mapping_spec.json --collections <unit> --tolerances .migration/recon_tolerances.json --canonicalization <plugin>/skills/mongo-migration/profiles/oracle.md --mode live --target-class migration_cluster --source-dsn-secret MMP_RT_SRC_DSN --target-uri-secret MONGODB_ATLAS_URI --target-db mmp_rt_b3_oracle --allowed-targets-file .migration/allowed_targets.json --source-concurrency 1 --seed 1`. Verifier artifacts live under `.migration/recon/wave-1/<batch>/<unit>/` and never touch the batch artifacts under `.migration/recon/<unit>/`. Console log: `evidence/recon_run.log`.

| batch | unit | batch artifact: mapping / verdict / merge | verifier: verdict / merge | tier checks 1/2/3 | Tier-3 population | warnings | verifier call | result.json sha256[:16] |
|---|---|---|---|---|---|---|---|---|
| w1-b01 | `codes` | map-draft-3 / PASS / y | **PASS** / y | 2/0/32 | 32 | 0 | PASS | `f8d469f3b98d5e9c` |
| w1-b01 | `tenants` | map-draft-3 / PASS / y | **PASS** / y | 2/2/15 | 15 | 0 | PASS | `0b6ee6044f09fa26` |
| w1-b01 | `plans` | map-draft-3 / PASS / y | **PASS** / y | 3/5/3 | 3 | 0 | PASS | `1bf6a3202a4c7e73` |
| w1-b01 | `customerMaster` | map-draft-3 / PASS / y | **PASS** / y | 3/15/271 | 201 | 0 | PASS | `665cc066614cb956` |
| w1-b01 | `billingAuditLog` | map-draft-3 / PASS / y | **PASS** / y | 1/1/0 | 0 | 0 | UNVERIFIED | `945df31ea642a2c1` |
| w1-b02 | `ratingPeriods` | map-draft-3 / PASS / y | **PASS** / y | 3/2/3 | 3 | 0 | PASS | `db6835c756d96caa` |
| w1-b02 | `creditNotes` | map-draft-3 / PASS / y | **PASS** / y | 3/3/5 | 5 | 0 | PASS | `8baef1f62ada9968` |
| w1-b02 | `usageEvents` | map-draft-3 / PASS / y | **PASS** / y | 2/3/103 | 103 | 0 | PASS | `838fd6bfc8363432` |
| w1-b02 | `notifications` | map-draft-3 / PASS / y | **PASS** / y | 2/2/1 | 1 | 0 | PASS | `9b7e0648f57e4975` |
| w1-b02 | `subscriptions` | map-draft-3 / PASS / y | **PASS** / y | 4/2/30 | 15 | 0 | PASS | `0151010e2f2dbd23` |
| w1-b03 | `invoiceHeader` | map-draft-4 / PASS / n | **PASS** / n | 3/2/2463 | 1000 | 1 | PASS | `a76422c735305fcf` |
| w1-b03 | `customerMasterHist` | map-draft-3 / PASS / y | **PASS** / y | 2/15/0 | 0 | 0 | UNVERIFIED | `943e64e2054a9d10` |
| w1-b04 | `invoices` | map-draft-4 / PASS / y | **PASS** / y | 5/5/12 | 4 | 0 | PASS | `5ff44513cc350f14` |
| w1-b04 | `subscriptionsHist` | map-draft-4 / PASS / y | **PASS** / y | 2/1/0 | 0 | 0 | UNVERIFIED | `4bd2400565598881` |
| w1-b04 | `ratingResults` | map-draft-4 / PASS / y | **PASS** / y | 2/6/3 | 3 | 0 | PASS | `a85aa12c2b9c4509` |
| w1-b05 | `dunningAttempts` | map-draft-4 / PASS / y | **PASS** / y | 2/3/1 | 1 | 0 | PASS | `73a44dda4d70dc78` |

Verdict change between mapping versions: none (16/16 PASS under both the batch's cited version and `map-draft-4`). `merge_eligible` differs from the batch artifact for no unit.

## 4. Probes past the gate (`evidence/probe.py` → `evidence/probes.json`)

### 4.1 Orphan-line disposition and scoped-embed safety (INVOICE_HEADER → INVOICE_LINE)

| check | value |
|---|---|
| `sum(len(invoiceHeader.lines))` | **1463** |
| `count(invoice_lines_orphaned)` | **37** |
| sum | **1500** == `COUNT(*) INVOICE_LINE` 1500 |
| source rows inside `child_where` / outside | 1463 / 37 |
| embedded `lineId` set == source in-scope `LINE_ID` set | True |
| orphan-sink `lineId` set == source orphan `LINE_ID` set | True |
| embedded elements whose INVOICE_LINE row is outside `child_where` ("extra target elements not checked") | **0** |
| `lineId` on both sides | **0** |
| distinct orphan `invoiceId` / resolving to a header on source / on target | 37 / **0** / **0** |
| orphan docs with `orphan: true` / raw `invoiceId` present | 37 / 37 |
| per-header `len(lines)` ≠ source child count | 0 (line-less headers 232 source / 232 target) |
| embedded scalar field mismatches (invoiceNo, custId, lineNo, lineTypeCd, itemDesc, qty, amount, posted, batchNo) | 0 |

### 4.2 Embed-array lengths vs child rows

- `customerMaster.attributes` vs ENTITY_ATTR_VALUE: sum 70 == 70 rows (all `entity_type = CUSTOMER`, 0 rows without a customer), per-customer mismatches 0; every element has shape `('createdDt', 'createdDtRaw', 'eavId', 'entityType', 'k', 'type', 'v')` (F62's duplicate `(ENTITY_ID, ATTR_NAME)` pair is kept as two elements).
- `invoices.lines` vs INVOICE_LINES: sum 4 == 4 rows, mismatches []; element shape `('amount', 'description', 'id', 'lineNo', 'lineType')`; the `lines.lineNo` index exists and `lineNo` is populated on both invoices that have lines.

### 4.3 Counts, duplicate keys, key nulls, indexes, unmapped target fields

| collection | source rows | target docs | exists | dup keys | key null/missing | indexes | unmapped target fields | fields with null-rate note |
|---|---|---|---|---|---|---|---|---|
| `billingAuditLog` | 0 | 0 | **no** | 0 | 0 | 0 | - | 0 |
| `codes` | 32 | 32 | yes | 0 | 0 | 2 | - | 0 |
| `creditNotes` | 5 | 5 | yes | 0 | 0 | 3 | - | 0 |
| `customerMaster` | 201 | 201 | yes | 0 | 0 | 2 | `signupDtRaw`, `lastActivityDtRaw`, `tenantResolved` | 1 |
| `customerMasterHist` | 0 | 0 | yes | 0 | 0 | 2 | - | 0 |
| `dunningAttempts` | 1 | 1 | yes | 0 | 0 | 2 | - | 0 |
| `invoiceHeader` | 1000 | 1000 | yes | 0 | 0 | 2 | `invoiceDtRaw`, `dueDtRaw` | 0 |
| `invoices` | 4 | 4 | yes | 0 | 0 | 4 | - | 0 |
| `notifications` | 1 | 1 | yes | 0 | 0 | 2 | - | 0 |
| `plans` | 3 | 3 | yes | 0 | 0 | 3 | - | 0 |
| `ratingPeriods` | 3 | 3 | yes | 0 | 0 | 2 | - | 0 |
| `ratingResults` | 3 | 3 | yes | 0 | 0 | 2 | - | 0 |
| `subscriptions` | 15 | 15 | yes | 0 | 0 | 4 | - | 0 |
| `subscriptionsHist` | 0 | 0 | yes | 0 | 0 | 2 | - | 0 |
| `tenants` | 15 | 15 | yes | 0 | 0 | 2 | - | 0 |
| `usageEvents` | 103 | 103 | yes | 0 | 0 | 2 | - | 0 |

Null/missing per field: for every mapped field of every non-empty unit, `target missing + null == source NULL (or empty-string for empty_string_is_null)` except `customerMaster.signupDt` (target missing 41, source NULL 0): the 41 are the fixture's planted dirty dates nulled by the `date_string_to_date:dby-b3d57e-unparseable-null` alias (F61) — see 4.6 and F75. Full per-field table in `evidence/probes.json → per_collection.*.fields`.

### 4.4 Boundary documents

min/max compared for every `date`/`decimal`/`long` field of every non-empty unit (datetime fields to the millisecond, decimals at 2 dp): **0 mismatches** (`evidence/probes.json → boundaries`).

### 4.5 Empty collections

`billingAuditLog` — collection absent on the target (never created); `customerMasterHist`, `subscriptionsHist` — present, 0 docs, unique index only. All three have 0 source rows. See 4.9.

### 4.6 Dirty-date flags (string-date columns)

| field | rule | target date | string | null | missing | source non-null | source not `DD-MON-YY` shape | sibling raw field |
|---|---|---|---|---|---|---|---|---|
| `customerMaster.signupDt` | `date_string_to_date:dby-b3d57e-unparseable-null` | 160 | 0 | 41 | 41 | 201 | 24 | signupDtRaw |
| `customerMaster.lastActivityDt` | `date_string_to_date:dby-b3d57e` | 201 | 0 | 0 | 0 | 201 | 0 | lastActivityDtRaw |
| `customerMaster.lastInvoiceDt` | `date_string_to_date` | 0 | 0 | 201 | 201 | 0 | 0 | - |
| `customerMaster.lastPaymentDt` | `date_string_to_date` | 0 | 0 | 201 | 201 | 0 | 0 | - |
| `customerMaster.terminateDt` | `date_string_to_date` | 0 | 0 | 201 | 201 | 0 | 0 | - |
| `invoiceHeader.invoiceDt` | `date_string_to_date:dby-b3d57e` | 1000 | 0 | 0 | 0 | 1000 | 0 | invoiceDtRaw |
| `invoiceHeader.dueDt` | `date_string_to_date:dby-b3d57e` | 1000 | 0 | 0 | 0 | 1000 | 0 | dueDtRaw |
| `invoiceHeader.lines.invoiceDt` | `-` | 1463 | 0 | 0 | 0 | - | 0 | - |

`signupDt`: the 41 dropped raw values (kept only in loader-only `signupDtRaw`) are `N/A`×6, `12-13-201`×6, `  -   -  `×6, `99-999-99`×2, `1/1/1900`×4 (parses under `%m/%d/%Y`), and the shape-conformant but calendar-impossible `31-FEB-24`×6, `29-FEB-23`×4, `00-XXX-00`×7. Both the loader and the harness canon apply the same alias, so the drop is symmetric and no tier can see it (F75). `lastInvoiceDt`/`lastPaymentDt`/`terminateDt` carry the bare `date_string_to_date` rule over 0 non-null values — the same unexercised shape as F73.

### 4.7 Codes

`codes` == `CODES`: 32 rows / 32 docs, key set equal True, `codeDesc` mismatches 0, `codeVal` stored as Int64. Code columns against their CODES domain (labels are DECODEs in the packages, F30/F53):

| field | CODES type | target values | outside domain |
|---|---|---|---|
| `tenants.statusCd` | TENANT_STATUS | {'10': 14, '20': 1} | none |
| `invoices.statusCd` | INV_STATUS | {'40': 2, '20': 1, '30': 1} | none |
| `plans.tierCd` | PLAN_TIER | {'1': 1, '2': 1, '3': 1} | none |
| `subscriptions.statusCd` | SUB_STATUS | {'10': 14, '20': 1} | none |
| `usageEvents.kindCd` | USAGE_KIND | {'1': 70, '3': 12, '2': 21} | none |
| `notifications.kindCd` | NOTIF_KIND | {'2': 1} | none |
| `invoiceHeader.statusCd` | INV_STATUS | {'30': 541, '40': 150, '20': 309} | none |
| `customerMaster.statusCd` | CUST_STATUS | {'1': 168, '3': 9, '2': 22, '99': 2} | none |
| `dunningAttempts.statusCd` | DUN_STATUS | {'20': 1} | none (domain 10/20/30) |

### 4.8 Cross-unit references and extended-reference copies

| edge | target dangling (distinct) | source dangling (distinct) | equal |
|---|---|---|---|
| `invoiceHeader.custId->customerMaster` | 0 | 0 | yes |
| `invoiceHeader.tenantId->tenants` | 11 | 11 | yes |
| `customerMaster.tenantId->tenants` | 18 | 18 | yes |
| `subscriptions.planId->plans` | 0 | 0 | yes |
| `subscriptions.tenantId->tenants` | 0 | 0 | yes |
| `invoices.tenantId->tenants` | 0 | 0 | yes |
| `invoices.periodId->ratingPeriods` | 0 | 0 | yes |
| `dunningAttempts.invoiceId->invoices` | 0 | 0 | yes |
| `ratingResults.subscriptionId->subscriptions` | 0 | 0 | yes |
| `ratingResults.periodId->ratingPeriods` | 0 | 0 | yes |
| `usageEvents.tenantId->tenants` | 0 | 0 | yes |
| `creditNotes.tenantId->tenants` | 0 | 0 | yes |
| `notifications.tenantId->tenants` | 0 | 0 | yes |
| `copied.invoices.tenant.statusCd_vs_tenants` | 0 | 0 | yes |
| `copied.subscriptions.plan_vs_plans` | 0 | 0 | yes |

`customerMaster.tenantResolved` is `false` on 200/201 documents — consistent with the 18 dangling tenant ids; loader-only field, not in the spec (F75/F77).

### 4.9 Zero-row units → UNVERIFIED

| unit | harness | why UNVERIFIED |
|---|---|---|
| `billingAuditLog` | PASS / merge_eligible true (Tier 1 1 check, Tier 2 1, Tier 3 0, population 0) | source 0 rows; target collection never created (F68/F70) |
| `customerMasterHist` | PASS / merge_eligible true (population 0) | source 0 rows; empty collection + index only (F70) |
| `subscriptionsHist` | PASS / merge_eligible true (population 0) | source 0 rows; TRG_SUBSCRIPTIONS_HIST never fired in the fixture (F73) |

The composite keys, history-copy shapes and every field rule of these three units remain unexercised by the whole wave.

### 4.10 F73 — `subscriptionsHist.histDt` latent defect (confirmed, not fixed)

`01_tables.sql`: `TRG_SUBSCRIPTIONS_HIST … AFTER UPDATE OR DELETE ON subscriptions` writes `DD-MON-YY HH24:MI:SS` into `hist_dt      VARCHAR2(20)`; `mapping_spec.json` `subscriptionsHist.fields[HIST_DT]` → `histDt` `date` with rules `['date_string_to_date', 'null_missing_equiv']` (bare rule, default `%d-%b-%y`, no `format` param). SUBSCRIPTIONS_HIST rows = 0. Defect latent: **True**.

### 4.11 F74 — fixture-first artifacts

| unit | `recon/<unit>/fixture/result.json` | fixture mapping | batch live mapping | wave pin |
|---|---|---|---|---|
| `billingAuditLog` | yes | map-draft-2 | map-draft-3 | map-draft-4 |
| `codes` | yes | map-draft-2 | map-draft-3 | map-draft-4 |
| `creditNotes` | yes | map-draft-3 | map-draft-3 | map-draft-4 |
| `customerMaster` | yes | map-draft-2 | map-draft-3 | map-draft-4 |
| `customerMasterHist` | yes | map-draft-3 | map-draft-3 | map-draft-4 |
| `dunningAttempts` | yes | map-draft-4 | map-draft-4 | map-draft-4 |
| `invoiceHeader` | yes | map-draft-4 | map-draft-4 | map-draft-4 |
| `invoices` | yes | map-draft-4 | map-draft-4 | map-draft-4 |
| `notifications` | yes | map-draft-3 | map-draft-3 | map-draft-4 |
| `plans` | yes | map-draft-2 | map-draft-3 | map-draft-4 |
| `ratingPeriods` | yes | map-draft-3 | map-draft-3 | map-draft-4 |
| `ratingResults` | yes | map-draft-4 | map-draft-4 | map-draft-4 |
| `subscriptions` | yes | map-draft-3 | map-draft-3 | map-draft-4 |
| `subscriptionsHist` | yes | map-draft-4 | map-draft-4 | map-draft-4 |
| `tenants` | yes | map-draft-2 | map-draft-3 | map-draft-4 |
| `usageEvents` | yes | map-draft-3 | map-draft-3 | map-draft-4 |

Missing: **none** (16/16 present). Stale against the pin: 11 fixture artifacts (5 `map-draft-2`, 6 `map-draft-3`) and 11 batch live artifacts (`map-draft-3`) — F76.

## 5. App-level parity replays (`evidence/parity.py` → `evidence/parity.json`)

The read-only principal has no EXECUTE on the packages, so each function's cursor SQL (read from `04_pkg_invoicing.sql`, `05_pkg_dunning.sql`, `02_pkg_plans.sql`) was replayed verbatim on the source and its document-model equivalent on the target; result rows were compared, not summaries.

- `fn_invoice_lines(p_invoice_id)` — all 4 INVOICES ids: source rows [2, 0, 0, 2] vs target `lines` [2, 0, 0, 2]; exact match including `line_no` order: True.
- `fn_overdue_accounts(p_as_of)` — as-of 5 dates (2026-10-07, 2025-01-01, 2099-12-31, 2026-02-14, 2026-02-01): source/target rows [(2, 2), (0, 0), (2, 2), (2, 2), (0, 0)]; equal using the copied `invoices.tenant.statusCd`: True; equal using a `tenants` lookup instead: True (tenant_id, invoice_id, total, days_overdue, tenant_status compared per row in `ORDER BY issued_at, id`).
- `fn_entitlement(p_tenant_id, p_on)` — 45 cases (15 tenants × 3 dates incl. every distinct `starts_on` boundary and the day after the latest), 45 non-empty on the source, mismatches **0** (plan_code, tier, monthly_fee, included_units, subscription_status, effective_on); `ROWNUM <= 1` tie risk (same tenant + starts_on): 0 groups.

## 6. Findings (one sentence each; F75–F77 are new and appended to `.migration/05_decisions.md`)

- F75: loader-only target fields (`customerMaster.signupDtRaw`/`lastActivityDtRaw`/`tenantResolved`, `invoiceHeader.invoiceDtRaw`/`dueDtRaw`, `attributes[].createdDtRaw`/`eavId`) are outside the spec and the harness has no unmapped-field check, so the 41 `signupDt` values the `unparseable: null` alias drops (24 non-shape incl. 4 x `1/1/1900`, 17 shape-conformant but calendar-impossible) are symmetric on both sides and invisible to every tier; proven only by hand.
- F76 (observed): `preflight.py --grade` on the five committed batch results under manifest b11c0e7b2f31 downgrades w1-b01, w1-b02 and w1-b03 to FAIL `insufficient_evidence` because their cited result.json files grade `map-draft-3` (b03: customerMasterHist not re-run), so only w1-b04 and w1-b05 are gradable PASS batches today although all three were merged into the run branch; the verifier's own 16 live runs under map-draft-4 are PASS for every unit of all five batches.
- F76: the F74 check finds all 16 fixture-first artifacts present, but 11 fixture and 11 batch live `result.json` cite `map-draft-2`/`map-draft-3` while the wave pins `map-draft-4`, and `preflight.py:314` grades against the batch ticket's pin, not the wave's; the verifier's 16 re-runs under `map-draft-4`/tolerances 1 all PASS with no verdict change between versions.
- F77: no tier grades cross-unit reference resolution: 200/201 `customerMaster.tenantId` (18 distinct) and 11 distinct `invoiceHeader.tenantId` values resolve to no `tenants` document, identical on the source (horror tenant ids, F19), so a fixture property not a load defect; 13 reference edges and both extended-reference copies were checked by hand and are equal on both sides.
- F70/F68 re-confirmed under map-draft-4: `billingAuditLog` (collection never created), `customerMasterHist` and `subscriptionsHist` are harness PASS / merge_eligible true on 0 rows and are reported UNVERIFIED here, not PASS.
- F72 re-confirmed: `invoiceHeader` is PASS / merge_eligible false on the scoped embed warning; the hand proof holds (1463 + 37 = 1500, 0 lineIds on both sides, 0 embedded elements outside child_where, 37 orphan invoiceIds resolve to no header on either side).
- F73 confirmed by reading `01_tables.sql` and the spec: the trigger writes `TO_CHAR(SYSDATE, 'DD-MON-YY HH24:MI:SS')` into `HIST_DT VARCHAR2(20)` and the spec maps `histDt` with the bare `date_string_to_date` rule; 0 rows hide it; not fixed.
- F63(b) in force: every verifier live run printed the unsalted-redaction warning and wrote `redaction_salted: false`; `RECON_REDACT_SALT` is still named by no skill or ticket.

## 6a. `preflight.py --grade … --verify` (run by the verifier against the pushed branch)

`GIT_DIR=<repo>/.git python3 <plugin>/skills/wave-preflight/preflight.py --wave .migration/waves/wave-1.json --root <repo> --grade .migration/recon/w1-b0{1..5}.batch.json --verify .migration/recon/wave-1/verify-result.json --run-id ticket-cf5c46af9c3345b98534ff860bb73f38` → graded PASS set `{w1-b04, w1-b05}`, b01–b03 `FAIL insufficient_evidence` as described above; `verify_problems: []` once `unit_verdicts` was keyed to that set (output in `evidence/preflight_verify.out`). The branch `recon/wave-1` already existed on origin from an unrelated 2026-09-29 run (off `32baffd8`); it was merged in (its `report.md` removed) rather than force-pushed, so the branch advanced fast-forward.

## 7. Pre-PR self-check (`.agents/skills/tp-pre-pr-self-check`)

- NULL/missing attribution: checked per field in §4.3; the one asymmetry (`signupDt`, 41) is attributed to the planted dirty values and recorded (F61/F75), not failed open.
- Namespace scoping: this ticket writes only `.migration/recon/wave-1/**` and `05_decisions.md`; the target was read only (`mmp_rt_b3_oracle`), no `ow_tp` prefix applies to a verifier.
- No DDL, no drops, no alters: nothing executed but SELECTs and reads; §2 proves the target is byte-identical.
- Retention / cleanup / idempotency: not applicable (verifier writes nothing to any platform); the recon runs are repeatable and were run once each.
- Secrets: referenced by name only (`MMP_RT_SRC_DSN`, `MONGODB_ATLAS_URI`); artifacts are harness-redacted (unsalted, F63b).
- Parity vs tolerance decision: from the committed `recon_tolerances.json` v1 (sha above), unchanged.
- Recon values recomputed from the target platform: yes, every number here comes from this session's runs and probes.
- Unverified paths: `billingAuditLog`, `customerMasterHist`, `subscriptionsHist` (§4.9); the 37-row remainder is graded by hand only (§4.1); extra-field coverage is by hand only (F75).
- `"kind": "recon-report"` `*.recon.json`: not used — the wave-verify contract is the verify-result JSON validated by `preflight.py --verify`.
- Capability preflight: `connectivity.json` is `blocked: true` by human decision `d-target-principal` and was not edited; the live target reads succeeded regardless.
- `make tp-smoke`: green (`evidence/tp-smoke.log`; needed `mise trust` on the fresh VM first).

## 8. Evidence files on this branch

`verify-result.json` (manager contract), `evidence/probes.json` + `evidence/probe.py`, `evidence/parity.json` + `evidence/parity.py`, `evidence/fixture_counts_check.json`, `evidence/target_before.json` / `target_after.json` / `target_snapshot_compare.json`, `evidence/recon_run.log`, `evidence/tp-smoke.log`, and the 16 harness artifact sets under `w1-b0N/<unit>/{result.json,report.md,recon.summary.md}`.
