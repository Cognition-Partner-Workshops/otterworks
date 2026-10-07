run_id: UNT8-18
manifest_sha: 55e68257b3f9

# Wave 1 independent verification — OtterWorks Oracle billing → MongoDB Atlas (`mmp_rt_b4_oracle`)

- Run branch verified: `tp-run/mongodb-20261007T161014Z` @ `7e66c71a` (fresh clone `~/verify-w1`, branch `recon/wave-1-UNT8-18` (see finding on the `recon/wave-1` name collision); the batch worker's tree was never used).
- Contracts: mapping map-v1.1 sha256 `3dc4060d3a4bdc39f0904c3e79eff2568fb32e5560cad822280a0aa95b2539b6`, tolerances tol-1 sha256 `a23d517a8e6d00c84f668c0016ef0e42b16625d45ab7e4166e3838abf241e3da` — recomputed from the committed bytes in the clone and matched by every result.json below.
- Harness: mongo-recon-harness 0.3.3 from `~/mmp` @ `353280fc837193a40ccc005cb62fb4ffaf8ac16f` (unpatched), one `--mode live --target-class migration_cluster --source-concurrency 1` run per unit, `MMP_RT_SRC_DSN` / `MONGODB_ATLAS_URI` by name. The verifier wrote nothing to Atlas: no loader, no drop, no index; the harness and every probe are read-only (SELECT/aggregate/dbStats).
- Axes: source_access live (Oracle fixture `otterworks-oracle-billing-oracle-billing-1`, post-exercise mmprt mini seed), target_access migration_cluster. No live mismatch occurred, so no source re-run / drift call was needed.

## Verdict

**wave_verdict: PASS** — verifier batch verdicts (`verifier_batch_verdicts`): w1-b0-reference PASS, w1-b1-detached-depth0 PASS (on the three live-PASS units u06/u07/u09; u08 UNVERIFIED), w1-b2-tenant-children-depth1 PASS, w1-b3-rating-invoicing-depth2 PASS. `unit_verdicts` in `wave-1-verify.json` is keyed on exactly the pinned grader's PASS set — w1-b0-reference, w1-b2-tenant-children-depth1, w1-b3-rating-invoicing-depth2 — because `preflight.py --grade` grades w1-b1-detached-depth0 FAIL/insufficient_evidence for the UNVERIFIED u08 (merged under d-unverified-batch-merge). u08-customer-master-hist is **UNVERIFIED** (0 source rows), reported as such — not PASS, not FAIL.

## Independence caveat — shared fixture host

The verifier ran on the same VM as the batch worker. What that does **not** weaken: the clone is fresh from origin at 7e66c71a in a separate directory, the recon re-runs use the committed spec/tolerance bytes (sha256 verified), no load step was executed, the harness is pinned and unpatched, and every number here is read from the verifier's own result.json / probe files. What it **does** weaken: the Oracle fixture volume, the `MMP_RT_SRC_DSN` export, the Atlas principal (`MONGODB_ATLAS_URI`, org-shared), `~/mmp` and `~/.venvs/mmp` are the same artefacts the worker used, so a host-level defect or tampering common to both would not be detected; the source is a seeded fixture, not the production estate.

## Recon re-runs (one live run per unit)

| batch | unit | collections | verdict | merge_eligible | tiers | warnings |
|---|---|---|---|---|---|---|
| w1-b0-reference | u00-reference | codes, tenants, plans | **PASS** | True | T1 12 checks, 0 findings / T2 7 checks, 0 findings / T3 55 checks, 0 findings / T4 3 checks, 0 findings | — |
| w1-b1-detached-depth0 | u06-audit-log | billingAuditLog | **PASS** | True | T1 2 checks, 0 findings / T2 1 checks, 0 findings / T3 73 checks, 0 findings / T4 2 checks, 0 findings | — |
| w1-b1-detached-depth0 | u07-customer-master | customerMaster | **PASS** | True | T1 4 checks, 0 findings / T2 20 checks, 0 findings / T3 271 checks, 0 findings / T4 3 checks, 0 findings | — |
| w1-b1-detached-depth0 | u08-customer-master-hist | customerMasterHist | **UNVERIFIED** | False | T1 2 checks, 0 findings / T2 21 checks, 0 findings / T3 0 checks, 0 findings / T4 2 checks, 0 findings | UNVERIFIED collection customerMasterHist: 0 source rows, key/shape/field rules unexercised |
| w1-b1-detached-depth0 | u09-custbill-invoices | invoiceHeader, invoiceLine | **PASS** | True | T1 2 checks, 0 findings / T2 8 checks, 0 findings / T3 2500 checks, 0 findings / T4 3 checks, 0 findings | — |
| w1-b2-tenant-children-depth1 | u01-subscriptions | subscriptions, subscriptionsHist | **PASS** | True | T1 6 checks, 0 findings / T2 4 checks, 0 findings / T3 26 checks, 0 findings / T4 3 checks, 0 findings | — |
| w1-b2-tenant-children-depth1 | u02-usage-events | usageEvents | **PASS** | True | T1 2 checks, 0 findings / T2 3 checks, 0 findings / T3 103 checks, 0 findings / T4 3 checks, 0 findings | — |
| w1-b2-tenant-children-depth1 | u05-notifications | notifications | **PASS** | True | T1 2 checks, 0 findings / T2 2 checks, 0 findings / T3 2 checks, 0 findings / T4 2 checks, 0 findings | — |
| w1-b3-rating-invoicing-depth2 | u03-rating | ratingPeriods, ratingResults | **PASS** | True | T1 4 checks, 0 findings / T2 8 checks, 0 findings / T3 16 checks, 0 findings / T4 3 checks, 0 findings | — |
| w1-b3-rating-invoicing-depth2 | u04-invoices | invoices | **PASS** | True | T1 9 checks, 0 findings / T2 5 checks, 0 findings / T3 43 checks, 0 findings / T4 3 checks, 0 findings | — |

Merged batch PRs re-verified: w1-b0-reference (PR #1934 → d6fbff71); w1-b1-detached-depth0 (PR #1935 → 11ef9735); w1-b2-tenant-children-depth1 (PR #1936 → 481a730d); w1-b3-rating-invoicing-depth2 (PR #1937 → 7e66c71a).

## Probes past the gate

### Root counts (Oracle COUNT(*) vs target documents)

| collection | source table | source rows | target docs | |
|---|---|---|---|---|
| billingAuditLog | BILLING_AUDIT_LOG | 73 | 73 | ok |
| codes | CODES | 32 | 32 | ok |
| customerMaster | CUSTOMER_MASTER | 201 | 201 | ok |
| customerMasterHist | CUSTOMER_MASTER_HIST | 0 | 0 | ok |
| invoiceHeader | INVOICE_HEADER | 1000 | 1000 | ok |
| invoiceLine | INVOICE_LINE | 1500 | 1500 | ok |
| invoices | INVOICES | 9 | 9 | ok |
| notifications | NOTIFICATIONS | 2 | 2 | ok |
| plans | PLANS | 3 | 3 | ok |
| ratingPeriods | RATING_PERIODS | 8 | 8 | ok |
| ratingResults | RATING_RESULTS | 8 | 8 | ok |
| subscriptions | SUBSCRIPTIONS | 20 | 20 | ok |
| subscriptionsHist | SUBSCRIPTIONS_HIST | 6 | 6 | ok |
| tenants | TENANTS | 15 | 15 | ok |
| usageEvents | USAGE_EVENTS | 103 | 103 | ok |

### Embed array lengths vs child rows

| embed | child table | child rows | embedded elements | length distribution (len: docs) | |
|---|---|---|---|---|---|
| invoices.lines | INVOICE_LINES | 29 | 29 | {"0": 2, "2": 2, "5": 5} | ok |
| invoices.dunningAttempts | DUNNING_ATTEMPTS | 5 | 5 | {"0": 7, "2": 1, "3": 1} | ok |
| tenants.creditNotes | CREDIT_NOTES | 5 | 5 | {"0": 12, "1": 1, "2": 2} | ok |
| customerMaster.attributes | ENTITY_ATTR_VALUE | 70 | 70 | {"0": 143, "1": 49, "2": 7, "3": 1, "4": 1} | ok |

Element keys: `invoices.lines` keyed by `lineNo`, `invoices.dunningAttempts` by `id`, `tenants.creditNotes` by `id`, `customerMaster.attributes` by `attrName` (EAV, 58 of 201 customers carry attributes); `dunningAttempts.statusCd` is BSON long on all 5 elements (no extended reference, per d-dun-status-cd).

### Duplicate natural keys (unique spec indexes)

{"notifications": {"tenantId,kindCd,sentAt": 0}, "plans": {"code": 0}, "ratingPeriods": {"tenantId,periodStart": 0}, "tenants": {"name": 0}} — 0 duplicates everywhere; `_id` is the source PRIMARY KEY on every root (duplicate_source_key_count 0 in every Tier-3 full diff).

### Null / missing-field rates (mapped fields)

- `billingAuditLog` (73 docs, 3 mapped fields): missing-field count 0; all-null fields 0; partially null none
- `codes` (32 docs, 1 mapped fields): missing-field count 0; all-null fields 0; partially null none
- `customerMaster` (201 docs, 159 mapped fields): missing-field count 0; all-null fields 112; partially null {"addrLine2": 71, "addrLine3": 130, "conversionBatchNo": 1, "countryCd": 200, "creditLimitAmt": 42, "dunningExempt": 200, "legacySysKey": 1, "ltdBilledAmt": 200, "mainframeAcctNo": 1, "phone2": 92, "phone2TypeCd": 1, "promoCodes": 60, "relatedAcctIds": 41, "signupDt": 41, "subStatusCd": 66, "ytdPaidAmt": 200}
- `customerMasterHist` (0 docs, 163 mapped fields): missing-field count 0; all-null fields 0; partially null none
- `invoiceHeader` (1000 docs, 10 mapped fields): missing-field count 0; all-null fields 0; partially null none
- `invoiceLine` (1500 docs, 20 mapped fields): missing-field count 0; all-null fields 0; partially null {"posted": 313}
- `invoices` (9 docs, 7 mapped fields): missing-field count 0; all-null fields 0; partially null none
- `notifications` (2 docs, 3 mapped fields): missing-field count 0; all-null fields 0; partially null none
- `plans` (3 docs, 6 mapped fields): missing-field count 0; all-null fields 0; partially null none
- `ratingPeriods` (8 docs, 3 mapped fields): missing-field count 0; all-null fields 0; partially null none
- `ratingResults` (8 docs, 8 mapped fields): missing-field count 0; all-null fields 0; partially null none
- `subscriptions` (20 docs, 6 mapped fields): missing-field count 0; all-null fields 0; partially null {"endsOn": 15, "suspendedOn": 18}
- `subscriptionsHist` (6 docs, 10 mapped fields): missing-field count 0; all-null fields 2; partially null none
- `tenants` (15 docs, 3 mapped fields): missing-field count 0; all-null fields 0; partially null none
- `usageEvents` (103 docs, 4 mapped fields): missing-field count 0; all-null fields 0; partially null none

### Planted orphans / empty collections

- invoiceLine ghost pointers: 37 target documents whose `invoiceId` is not an `invoiceHeader._id`; Oracle: 37 INVOICE_LINE rows without an INVOICE_HEADER parent. Pointer kept verbatim; no document-level orphan flag (graded by Tier-4 op `custbill-ghost-lines`).
- INVOICE_LINES / DUNNING_ATTEMPTS orphans in Oracle: 0 / 0 (none planted; the embed orphan branch is unexercised).
- customerMasterHist: 0 documents, indexes ['_id_', 'custId_1__id_1']; CUSTOMER_MASTER_HIST = 0 rows → UNVERIFIED.
- customerMaster.relatedAcctIds literal "NULL": 4 documents, each `["NULL", "NONE"]`; Oracle RELATED_ACCT_IDS `'NULL,NONE,'` on 4 rows.
- subscriptionsHist: 6 of 6 documents keep `histDtRaw`.

### Cross-unit references (target, resolved against the loaded collections)

| reference | refs | unresolved |
|---|---|---|
| billingAuditLog.tenantId | 0 | 0 |
| invoiceHeader.custId | 1000 | 0 |
| invoiceHeader.tenantId | 1000 | 1000 |
| invoiceLine.custId | 1500 | 0 |
| invoiceLine.invoiceId | 1500 | 37 |
| invoiceLine.tenantId | 1500 | 1500 |
| invoices.periodId | 9 | 0 |
| invoices.tenantId | 9 | 0 |
| notifications.tenantId | 2 | 0 |
| ratingPeriods.tenantId | 8 | 0 |
| ratingResults.periodId | 8 | 0 |
| ratingResults.subscriptionId | 8 | 0 |
| subscriptions.planId | 20 | 0 |
| subscriptions.tenantId | 20 | 0 |
| subscriptionsHist.id | 6 | 0 |
| subscriptionsHist.planId | 6 | 0 |
| subscriptionsHist.tenantId | 6 | 0 |
| usageEvents.subscriptionId | 0 | 0 |
| usageEvents.tenantId | 103 | 0 |

invoiceHeader/invoiceLine `tenantId` unresolved 1000/1500 is source-faithful (Oracle: 1000/1500 CUSTBILL rows resolve to no TENANTS row).

### Tier-4 app-level parity replayed by the verifier

27/27 ops match (27 ops replayed from .migration/ops/*.json: source_sql on Oracle (CURRENT_SCHEMA=OW_BILLING, read-only), target_pipeline on mmp_rt_b4_oracle, both canonicalized (decimal_round 2dp, UTC ms truncation, empty_string_is_null, null_missing_equiv) and compared as sorted multisets). Pipeline `$date` literals are parsed as BSON extended JSON; a first naive replay that passed them as strings returned 0 target rows for 2 ops and is recorded in `probes/tier4_replay.json`.

## dbStats — `mmp_rt_b4_oracle`

`{"avgObjSize": 590.8842281879195, "collections": 16, "dataSize": 1760835, "db": "mmp_rt_b4_oracle", "indexSize": 1105920, "indexes": 42, "objects": 2980, "storageSize": 1716224, "views": 0}`

mongosh (secret by name):
```
{
  db: 'mmp_rt_b4_oracle',
  collections: 16,
  objects: Long('2980'),
  dataSize: Long('1760835'),
  storageSize: Long('1716224'),
  indexes: 42,
  indexSize: Long('1122304')
}
```

Collections present: _connectivity_probe, billingAuditLog, codes, customerMaster, customerMasterHist, invoiceHeader, invoiceLine, invoices, notifications, plans, ratingPeriods, ratingResults, subscriptions, subscriptionsHist, tenants, usageEvents.

## Findings

1. w1-b1-detached-depth0: u08-customer-master-hist is UNVERIFIED (CUSTOMER_MASTER_HIST has 0 source rows; customerMasterHist has 0 documents and index custId_1__id_1), so the batch verdict rests on the three live PASS units under plan decision d-unverified-batch-merge and the pinned grader may still grade it insufficient_evidence.
2. w1-b1-detached-depth0: 4 customerMaster.relatedAcctIds arrays are ["NULL","NONE"] because the harness csv_to_array keeps the literal NULL token from RELATED_ACCT_IDS 'NULL,NONE,' while d-csv-to-array says to drop it (known mismatch, graded PASS by the harness, not changed).
3. w1-b1-detached-depth0: the 37 planted INVOICE_LINE ghost pointers landed as declared (37 invoiceLine.invoiceId values resolve to no invoiceHeader, matching 37 in Oracle); the pointer is kept verbatim and the orphan flag exists only as the Tier-4 op custbill-ghost-lines, not as a field on the document.
4. w1-b1-detached-depth0: all 1000 invoiceHeader.tenantId and 1500 invoiceLine.tenantId values resolve to no tenants document, which is source-faithful (the same 1000/1500 CUSTBILL rows resolve to no TENANTS row in Oracle; detached estate, see data profile).
5. w1-b1-detached-depth0: customerMaster.signupDt is null on 41 of 201 documents; every source SIGNUP_DT is non-ISO text (DD-MON-YY or 'N/A'), the raw copy is kept on all 201 documents, and the harness graded it PASS.
6. all batches: RECON_REDACT_SALT is not set on the fixture host, so all 10 verifier result.json files record redaction_salted=false (unsalted hashes, low-entropy values enumerable offline).
7. all batches: the verifier shared the fixture host with the batch worker (same machine, same Oracle fixture volume, same MMP_RT_SRC_DSN export, same Atlas principal, same ~/mmp and ~/.venvs/mmp); independence holds at the working-tree and process level (fresh clone at 7e66c71a, no loader run, read-only harness, sha256-verified spec bytes) but not at the host level.
8. w1-b2-tenant-children-depth1: usageEvents carries no subscriptionId in map-v1.1 (USAGE_EVENTS has none), so the subscription pointer check applies to ratingResults.subscriptionId (8/8 resolve) and subscriptionsHist.id (6/6 resolve) only.
9. cluster: mmp_rt_b4_oracle holds one empty collection outside the mapping, _connectivity_probe (0 docs, left by the UNT8-4 connectivity round-trip); no other unexpected collection or database write was observed.
10. all batches: the plugin's fixed verifier branch name recon/wave-1 collides across runs on the same repo (origin/recon/wave-1 already held another run's wave-1 evidence at 36873379, off 32baffd8, manifest b11c0e7b2f31), so this run's evidence lives on recon/wave-1-UNT8-18 by manager decision instead of force-pushing or merging foreign .migration/ content (to 05_decisions.md §5).
11. w1-b1-detached-depth0: the pinned grader (preflight.py --grade) grades this batch FAIL/insufficient_evidence because u08-customer-master-hist is UNVERIFIED, so unit_verdicts carries only the grader's PASS set (w1-b0, w1-b2, w1-b3) and the verifier's PASS for w1-b1 (three live-PASS units, u08 UNVERIFIED) is reported in verifier_batch_verdicts.
12. all batches: the pinned preflight.py --verify hard-codes branch recon/wave-1 in verify_report_path with no --report-branch override, so under the manager's option B (evidence on recon/wave-1-UNT8-18) it reports every result path and the report as "not committed on origin/recon/wave-1" — expected under the branch-name collision, recorded, not fixed.

## Evidence files on `recon/wave-1-UNT8-18`

report_path: `recon/wave-1-UNT8-18:.migration/recon/wave-1/verify-report.md`

- `.migration/recon/wave-1/<batch>/<unit>/result.json` (+ report.md, recon.summary.md) — the verifier's own runs (10 units).
- `.migration/recon/wave-1/probes/target_probes.json`, `source_probes.json`, `tier4_replay.json`, `dbstats_mongosh.txt`.
- `.migration/recon/wave-1/wave-1-verify.json` — the verify result JSON below.
