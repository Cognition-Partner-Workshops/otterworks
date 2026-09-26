# Recon report: unit `u-06-invoice-header-bulk`

- **Verdict: FAIL** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging) | Target: `local` (local target: NOT a merge verdict)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-2`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-26T18:07:10.184064+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | FAIL (1 findings) |

## Tier 1 coverage
```json
{
  "source_counts": {
    "invoiceHeader": 18750
  }
}
```

## Tier 1 findings (1)
- `invoiceHeader` embed_cardinality: rows(INVOICE_LINE)=150000 vs sum(len(lines))=149963
