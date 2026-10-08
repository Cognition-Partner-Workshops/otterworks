run_id: UNT9-7
manifest_sha: ec9a01d04e88

# Wave 1 independent verification — OtterWorks Oracle billing → MongoDB Atlas (`mmp_rt_b5_oracle`)

- Run branch verified: `tp-run/mongodb-20261008T120222Z` @ `36885ce7` (all 5 batch PRs merged: w1-b01 #1949, w1-b02 #1950, w1-b03 #1951, w1-b04 #1952, w1-b05 #1953); evidence branch `recon/wave-1-UNT9-7` (ticket branch rule; `recon/wave-1` holds another run).
- Contracts: mapping map-v3 sha256 `c158f8bb469d1e2733cfae5aa26e315d0ade4490f1164048ee161230c866dbd7`, tolerances tol-1 sha256 `a23d517a8e6d00c84f668c0016ef0e42b16625d45ab7e4166e3838abf241e3da` — recomputed from the committed bytes and matched by every result.json below.
- Harness: mongo-recon-harness 0.3.3 from the plugin pinned at `349cb2d17dccb246409e7750657e25843bf53be8` (unpatched), `recon selftest` PASS, one `--mode live --target-class migration_cluster --source-concurrency 1 --collections <unit collections>` run per unit, canonicalization `skills/mongo-migration/profiles/oracle.md`, secrets `MMP_RT_SRC_DSN` / `MONGODB_ATLAS_URI` by name. The verifier loaded nothing, merged nothing, wrote nothing to Atlas.
- Fixture: fresh host, fresh Oracle volume (`make oracle-billing-up`, port 52521), seeded with `DB_PORT=52521 uv run --with oracledb==2.5.1 testdata/legacy/mmp_rt_mini_seed.py`, exercised once with `testdata/legacy/mmp_rt_exercise.sql`; read-only COUNT(*) of all 20 tables equals `.migration/fixtures/mmprt-mini.json` row_counts (SUBSCRIPTIONS_HIST=6, BILLING_AUDIT_LOG=37, CUSTOMER_MASTER_HIST=0) — no count DRIFT.
- Target footprint: db.stats() on `mmp_rt_b5_oracle`: dataSize 1,428,179 B + indexSize 1,032,192 B = 2,460,371 B (< 10 MB), 17 collections, 3,022 objects; no other database touched.

## Verdict

**wave_verdict: FAIL** (grader form) — `unit_verdicts`: w1-b01 PASS, w1-b02 FAIL, w1-b03 FAIL, w1-b04 PASS, w1-b05 PASS.

**Verifier's verdicts (`verifier_batch_verdicts`): w1-b01 PASS, w1-b02 DRIFT-EXPLAINED, w1-b03 DRIFT-EXPLAINED, w1-b04 PASS, w1-b05 PASS.** The two FAIL re-runs differ from the target on exactly the two wall-clock columns the fixture exercise stamps with SYSDATE (`BILLING_AUDIT_LOG.LOGGED_AT` via pkg_ow_util.log_msg → all 37 `billingAuditLog.loggedAt`; `SUBSCRIPTIONS_HIST.HIST_DT` via TRG_SUBSCRIPTIONS_HIST → all 6 `subscriptionsHist.histDt`/`histDtRaw`): source 2026-10-08 13:32:23 (this host's exercise), target 2026-10-08 12:11:03 (the batch hosts' exercise). The source side was re-run twice more and did not move (same hashes, 37 and 12 findings each time): a fixture re-exercised on another host, not a defect in the loaders. The pinned `preflight.py validate_verify` accepts only PASS/FAIL, and a PASS must be graded from a PASS `result.json`, so `unit_verdicts` carries FAIL for those two batches; the manager decides what drift means for merged PRs.

**UNVERIFIED:** `customer-master` (w1-b01) for collection `customerMasterHist` — CUSTOMER_MASTER_HIST has 0 source rows, the collection does not exist on the target, key/shape/field rules unexercised; harness PASS with merge_eligible False. The batch verdict rests on the other four units and on `customerMaster` (201/201).

## Recon re-runs (one live run per unit; result.json beside this report)

| batch | unit | collections | verdict | merge_eligible | tiers | warnings |
|---|---|---|---|---|---|---|
| w1-b01 | customer-master | customerMasterHist,customerMaster | **PASS** | False | T1 2 checks, 0 findings / T2 32 checks, 0 findings / T3 201 checks, 0 findings | UNVERIFIED collection customerMasterHist: 0 source rows, key/shape/field rules unexercised |
| w1-b01 | entity-attr-value | entityAttrValue | **PASS** | True | T1 1 checks, 0 findings / T2 0 checks, 0 findings / T3 70 checks, 0 findings | — |
| w1-b01 | invoice-header | invoiceHeader | **PASS** | True | T1 1 checks, 0 findings / T2 2 checks, 0 findings / T3 1000 checks, 0 findings | — |
| w1-b01 | invoice-line | invoiceLine | **PASS** | True | T1 1 checks, 0 findings / T2 3 checks, 0 findings / T3 1500 checks, 0 findings | — |
| w1-b01 | reference-data | codes,tenants,plans | **PASS** | True | T1 6 checks, 0 findings / T2 7 checks, 0 findings / T3 50 checks, 0 findings | — |
| w1-b02 | billing-audit-log | billingAuditLog | **FAIL** | False | T1 1 checks, 0 findings / T2 1 checks, 2 findings / T3 37 checks, 37 findings | — |
| w1-b03 | credit-notes | creditNotes | **PASS** | True | T1 1 checks, 0 findings / T2 3 checks, 0 findings / T3 5 checks, 0 findings | — |
| w1-b03 | notifications | notifications | **PASS** | True | T1 2 checks, 0 findings / T2 2 checks, 0 findings / T3 2 checks, 0 findings | — |
| w1-b03 | rating-periods | ratingPeriods | **PASS** | True | T1 2 checks, 0 findings / T2 2 checks, 0 findings / T3 8 checks, 0 findings | — |
| w1-b03 | subscriptions | subscriptions,subscriptionsHist | **FAIL** | False | T1 5 checks, 0 findings / T2 4 checks, 0 findings / T3 46 checks, 12 findings | — |
| w1-b03 | usage-events | usageEvents | **PASS** | True | T1 2 checks, 0 findings / T2 3 checks, 0 findings / T3 103 checks, 0 findings | — |
| w1-b04 | invoices | invoices | **PASS** | True | T1 4 checks, 0 findings / T2 5 checks, 0 findings / T3 47 checks, 0 findings | — |
| w1-b04 | rating-results | ratingResults | **PASS** | True | T1 1 checks, 0 findings / T2 6 checks, 0 findings / T3 8 checks, 0 findings | — |
| w1-b05 | dunning-attempts | dunningAttempts | **PASS** | True | T1 2 checks, 0 findings / T2 3 checks, 0 findings / T3 3 checks, 0 findings | — |

## Probes past the gate (read-only)

| collection | source rows | target docs | duplicate keys | null/missing differs from source |
|---|---|---|---|---|
| ratingPeriods | 8 | 8 | 0 | — |
| customerMasterHist | 0 | absent | — | — |
| invoices | 9 | 9 | 0 | — |
| creditNotes | 5 | 5 | 0 | — |
| codes | 32 | 32 | 0 | — |
| tenants | 15 | 15 | 0 | — |
| plans | 3 | 3 | 0 | — |
| subscriptions | 20 | 20 | 0 | — |
| usageEvents | 103 | 103 | 0 | — |
| dunningAttempts | 3 | 3 | 0 | — |
| notifications | 2 | 2 | 0 | — |
| customerMaster | 201 | 201 | 0 | {'signupDt': [41, '0']} |
| entityAttrValue | 70 | 70 | 0 | — |
| invoiceHeader | 1000 | 1000 | 0 | — |
| invoiceLine | 1500 | 1500 | 0 | — |
| billingAuditLog | 37 | 37 | 0 | — |
| subscriptionsHist | 6 | 6 | 0 | — |
| ratingResults | 8 | 8 | 0 | — |

- Embed `invoices.lines` ← INVOICE_LINES: 29 child rows / 29 embedded, 7 parents with lines, per-parent length mismatches: none, length distribution {'2': 2, '0': 2, '5': 5} (2 invoices have 0 lines on both sides), child rows without parent: 0.
- Planted orphan pointers `invoiceLine.invoiceId` → no `invoiceHeader`: source 37 / target 37 — preserved verbatim.
- Cross-unit references (dangling source / target): subscriptions.tenantId->tenants 0/0 of 20; subscriptions.planId->plans 0/0 of 20; subscriptionsHist.id->subscriptions 0/0 of 6; usageEvents.tenantId->tenants 0/0 of 103; ratingResults.periodId->ratingPeriods 0/0 of 8; ratingResults.subscriptionId->subscriptions 0/0 of 8; invoices.periodId->ratingPeriods 0/0 of 9; invoices.tenantId->tenants 0/0 of 9; dunningAttempts.invoiceId->invoices 0/0 of 3; creditNotes.tenantId->tenants 0/0 of 5; notifications.tenantId->tenants 0/0 of 2; invoiceHeader.custId->customerMaster 0/0 of 1000; invoiceLine.custId->customerMaster 0/0 of 1500; entityAttrValue.entityId->customerMaster 0/0 of 70.
- Boundary keys (min/max source key found exactly once on target): {'invoiceHeader': {'000871b4-7c0a-dc91-8e9a-9c1db6b1d5f7': 1, 'ff16629f-44a2-5988-59e9-f8dddb2c1364': 1}, 'usageEvents': {'01083c3d-4389-06d8-e74e-5cd618eda819': 1, 'fefa0b2a-2156-f1be-3484-79e63262b911': 1}, 'billingAuditLog': {'1': 1, '37': 1}}.
- Collections present 17/18 write targets; missing ['customerMasterHist'] (0 source rows); unexpected: none.
- `customerMaster.signupDt` null on 41/201 where source is non-null text — map-v3 `date_string_to_date:dby-90c10b` unparseable→null with raw kept in `signupDtRaw` (plan decision d-date-unparseable); explained.
- Tier 4 / app-parity ops: none declared in `.migration/` for this run (no `ops/` directory), nothing to replay.

## Findings

1. w1-b02: the verifier's live re-run of billing-audit-log is FAIL on exactly one field — all 37 billingAuditLog.loggedAt values differ (source 2026-10-08 13:32:23, target 2026-10-08 12:11:03); LOGGED_AT is the wall-clock stamp pkg_ow_util.log_msg writes when testdata/legacy/mmp_rt_exercise.sql runs, the source value was identical across three re-runs (unit re-run twice more), keys, counts, module and message all match, so the batch is DRIFT-EXPLAINED (fixture re-exercised on a fresh host), recorded as FAIL in unit_verdicts because the pinned grader accepts only PASS/FAIL and a PASS must be graded from a PASS result.json.
2. w1-b03: the verifier's live re-run of subscriptions is FAIL on subscriptionsHist only — all 6 rows differ on histDt and histDtRaw (source '08-OCT-26 13:32:23', target '08-OCT-26 12:11:03'); HIST_DT is TO_CHAR(SYSDATE) written by TRG_SUBSCRIPTIONS_HIST when the exercise script closes the open subscriptions, the source value was identical across three re-runs, the other 4 units of the batch and the 20 subscriptions documents PASS with 0 findings, so the batch is DRIFT-EXPLAINED, recorded as FAIL in unit_verdicts for the same grader reason.
3. plugin/fixture: .migration/fixtures/mmprt-mini.json pins row counts but not the two wall-clock columns (BILLING_AUDIT_LOG.LOGGED_AT, SUBSCRIPTIONS_HIST.HIST_DT) that mmp_rt_exercise.sql stamps with SYSDATE, so the fixture is reproducible by count but not by value and an independent live re-verification on a fresh host can never PASS w1-b02 or the subscriptions unit of w1-b03 against a target loaded elsewhere; the exercise should stamp a fixed clock or the manifest should declare volatile columns for the recon to exclude.
4. plugin: skills/wave-verify/SKILL.md allows a per-batch DRIFT-EXPLAINED verdict, but skills/wave-preflight/preflight.py validate_verify rejects anything but PASS/FAIL per batch and for wave_verdict, so there is no grader-clean way to report drift; this run carries the drift verdicts in verifier_batch_verdicts beside the PASS/FAIL unit_verdicts.
5. plugin: preflight.py verify_report_path hard-codes recon/wave-1 with no branch override, so report_path 'recon/wave-1-UNT9-7:.migration/recon/wave-1/verify-report.md' (the branch rule of this ticket; recon/wave-1 holds another run's evidence) is rejected by --verify as 'report_path must be exactly recon/wave-1:...' — known mismatch, reported, branch not renamed.
6. plugin: the harness CLI requires --canonicalization, but the ticket's method command omits it; the verifier passed skills/mongo-migration/profiles/oracle.md from the pinned plugin clone (the harness skill's documented value), which the batch result.json files do not record, so canonicalization-file identity is not part of the evidence the grader checks.
7. w1-b01: customer-master is harness PASS with merge_eligible False because customerMasterHist has 0 source rows (CUSTOMER_MASTER_HIST=0 per the fixture manifest) and no collection on the target (17 of 18 write targets exist); the unit is UNVERIFIED for that collection — the fixture cannot exercise it — and the batch PASS rests on the four other live-PASS units plus the customerMaster collection (201/201, T3 201 checks, 0 findings).
8. w1-b01: customerMaster.signupDt is null/missing on 41 of 201 documents where the source SIGNUP_DT is non-null text ('N/A', '31-FEB-24', '00-XXX-00', '1/1/1900', ...); this is the map-v3 date_string_to_date:dby-90c10b unparseable->null rule with the raw text kept in signupDtRaw on all 201 documents (plan decision d-date-unparseable), graded PASS by the harness — explained, not a defect; every other field's null/missing count equals the source NULL count across all 17 collections.
9. all batches: probes past the gate found no defect — 17/17 collections match COUNT(*) exactly, 0 duplicate keys, invoices.lines embeds 29/29 INVOICE_LINES rows over 7 parents with identical per-parent lengths (2 invoices legitimately have 0 lines), the 37 planted invoiceLine.invoiceId orphans are preserved verbatim (37 source / 37 target), 14 cross-unit reference checks show 0 dangling pointers on both sides, boundary keys resolve once, and no unexpected collection exists in mmp_rt_b5_oracle.
10. all batches: RECON_REDACT_SALT is not set on this host, so all 14 verifier result.json files record redaction_salted=false (unsalted hashes; low-entropy values enumerable offline).
11. environment: the org blueprint note says the recon harness lives in /home/ubuntu/.venvs/recon, but on this fresh host the venv had no recon entry point (UNT9-1 finding reproduced); the verifier pip-installed mongo-recon-harness 0.3.3 from the pinned plugin clone into that venv and ran recon selftest (PASS, 9 rules) first.
12. manager contract: the verifier could not reproduce the manager's wave spec from the ticket block (eight canonical reconstructions hash to other values than ec9a01d04e88), so preflight.py --grade/--verify was run locally against a reconstructed spec only to capture the validator's problem list; the manifest_sha header is the one the ticket pins.
13. independence: fresh host, fresh clone of the run branch at 36885ce7, fresh Oracle volume seeded with mmp_rt_mini_seed.py and exercised once (row counts equal to the fixture manifest, no DRIFT on counts), no loader run, read-only harness and probes; the Atlas principal MONGODB_ATLAS_URI and the mapping/tolerance bytes are the same the batch workers used (sha256 verified).

## Evidence

- `.migration/recon/wave-1/wave-1-verify.json` — verify result (wave_verdict, unit_verdicts by batch id, recon_results, verifier_batch_verdicts, probes, dbStats).
- `.migration/recon/wave-1/<batch>/<unit>/result.json` — the verifier's 14 harness re-runs (overwriting the batch workers' files on this branch only).
