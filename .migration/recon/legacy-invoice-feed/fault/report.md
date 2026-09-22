# Recon report: unit `legacy-invoice-feed`

- **Verdict: FAIL** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-22T21:10:49.641395+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | FAIL (1 findings) |

## Tier 1 coverage
```json
{
  "source_counts": {
    "legacyInvoiceLines": 4000,
    "legacyInvoices": 500
  }
}
```

## Tier 1 findings (1)
- `legacyInvoiceLines` root_count: rows(INVOICE_LINE)=4000 vs docs=3999
