# Recon report: unit `w1-invoices`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-1`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-18T21:49:26.072012+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 5 | PASS |
| 2 | per_field_aggregates | 38 | PASS |
| 3 | keyed_diffs | 19764 | PASS |
| 4 | app_level_parity | 4 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "invoices": 3,
    "creditNotes": 5,
    "invoiceLine": 150000,
    "invoiceHeader": 18750
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "invoices.tenantId",
    "invoices.periodId",
    "invoices.subtotal",
    "invoices.tax",
    "invoices.total",
    "creditNotes.tenantId",
    "creditNotes.amount",
    "creditNotes.remainingAmount",
    "invoiceLine.invoiceNo",
    "invoiceLine.invoiceId",
    "invoiceLine.custId",
    "invoiceLine.custNo",
    "invoiceLine.custName",
    "invoiceLine.tenantId",
    "invoiceLine.lineNo",
    "invoiceLine.lineTypeCd",
    "invoiceLine.itemDesc",
    "invoiceLine.qty",
    "invoiceLine.qty",
    "invoiceLine.unitPrice",
    "invoiceLine.unitPrice",
    "invoiceLine.amount",
    "invoiceLine.amount",
    "invoiceLine.taxAmt",
    "invoiceLine.taxAmt",
    "invoiceLine.invoiceDt",
    "invoiceLine.servicePeriod",
    "invoiceLine.posted",
    "invoiceLine.glAcct",
    "invoiceLine.batchNo",
    "invoiceLine.srcSystem",
    "invoiceHeader.invoiceNo",
    "invoiceHeader.custId",
    "invoiceHeader.tenantId",
    "invoiceHeader.invoiceDt",
    "invoiceHeader.dueDt",
    "invoiceHeader.statusCd",
    "invoiceHeader.totalAmt",
    "invoiceHeader.totalAmt",
    "invoiceHeader.batchNo"
  ]
}
```

## Tier 3 coverage
```json
{
  "invoices": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  },
  "embeds_graded": {
    "invoices.lines": 2
  },
  "creditNotes": {
    "mode": "full_diff",
    "population": 5,
    "duplicate_source_key_count": 0
  },
  "invoiceLine": {
    "mode": "stratified_sample",
    "population": 150000,
    "sampled": 1004,
    "coverage": 0.006693,
    "duplicate_source_key_count": 0
  },
  "invoiceHeader": {
    "mode": "full_diff",
    "population": 18750,
    "duplicate_source_key_count": 0
  }
}
```
