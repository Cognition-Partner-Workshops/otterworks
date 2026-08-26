# Incident: MongoDB recon failure — ns=rehearsal invoices (2026-08-26)

## Summary

The scheduled-off, manually triggered MongoDB reconciliation for namespace
`rehearsal` failed and POSTed its remediation webhook. Five invoice documents
had been deleted from `ow_tp_mongodb_rehearsal.invoices` after migration.
Re-running the idempotent `mongo_invoices` migration for the namespace
restored the documents exactly; no code change was required and the baseline
manifest was never modified.

- Failing run: https://partner-workshops.devinenterprise.com/sessions/5bd4cfd2efba4b82812c6adf21bfb6c1
- Remediation run: https://partner-workshops.devinenterprise.com/sessions/a2218073e69c4cd394abbc4f26635d46

## Failing checks (webhook payload, reproduced locally)

`invoices-count`, `invoices-embedded-lines`, `invoice-lines-checksum`,
`invoice-lines-checksum-coverage`, `report-golden-parity`

Local re-run of `scripts/tp_mongo/showcase.py --ns rehearsal --run-mode live recon`
before the fix reproduced exactly those five ids:

```
FAIL invoices-count: expected 18750 actual 18745
FAIL invoices-embedded-lines: expected 149963 actual 149913
FAIL invoice-lines-checksum: expected "f716260a273b7568fb78d0588446cece"
                             actual   "8645de96321956261be8bacfaa176a9c"
FAIL invoice-lines-checksum-coverage: expected 150000 actual 149950
FAIL report-golden-parity: by_status[issued] invoice_count 5634 vs 5632, ... (headers missing from the aggregation)
```

## Root cause (evidence from the target collections)

Five invoice documents (`invoice_no` `REHEARSAL-000000000` …
`REHEARSAL-000000004`, 50 embedded lines) were deleted from
`ow_tp_mongodb_rehearsal.invoices` after the migration completed — an
out-of-band deletion recorded in the namespace's operational journal
collection at `2026-08-26T00:24:40Z`, ~34s after the green baseline capture.

Before the fix:

```
db.invoices.count_documents({ns:"rehearsal"})                       -> 18745  (manifest: 18750)
db.invoices.find({invoice_no:{$in:[REHEARSAL-000000000..004]}})     -> []     (0 of 5 present)
quarantine invoice_lines_quarantine count                            -> 37    (unchanged, matches manifest orphans)
customers / documents / document_snapshots / files counts            -> all matched baseline (undamaged)
```

The Oracle source estate (`OW_BILLING`, batch 15871060) still held all 18750
`INVOICE_HEADER` and 150000 `INVOICE_LINE` rows, so this was target-side data
loss, not a source reseed, validator regression, or migration-code defect.

## Remediation

Re-ran the idempotent invoice migration for the affected namespace only:

```
DB_PORT=52521 TP_MONGODB_URI=<atlas> migrations/mongodb/mongo_invoices/run.sh migrate --ns rehearsal
```

Document `_id`s are `uuid5` over the source keys, so the rerun upserted the
five missing invoices byte-identically and converged everywhere else
(`written.invoices: 18750`, `quarantined: 37`, `swept_stale: 0`). No target
document was hand-edited; the baseline manifest and legacy estate were not
touched.

## After (green proof)

`showcase.py --ns rehearsal --run-mode live recon` — `result: pass`,
`failed_checks: []`, 16/16 checks, including:

- `invoices-count` 18750 == 18750
- `invoice-lines-checksum` `f716260a273b7568fb78d0588446cece` (matches manifest)
- `invoice-lines-checksum-coverage` 150000 == 150000
- `report-golden-parity` — RPT-114 diff empty to the cent
- planted-anomaly / quarantine sets match exactly (missing: [], unexpected: [])
- `idempotency_rerun: pass` (checksum and report recomputed twice, identical);
  a second full migration rerun also converged with no changes

Recon schema validation: `make tp-validate-recon FILE=docs/tech-partnerships/recon/mongo_showcase.rehearsal.recon.json` → PASS.

Recon job re-trigger: `showcase.py --ns rehearsal --run-mode live run-job ...`
→ exit 0, `"notification": "not fired: reconciliation is green"`.

Full green report: [`../recon/mongo_showcase.rehearsal.recon.json`](../recon/mongo_showcase.rehearsal.recon.json).
Baseline capture: [`../recon/baseline/mongo_showcase.rehearsal.json`](../recon/baseline/mongo_showcase.rehearsal.json).
