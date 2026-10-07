# Recon report: unit `invoiceHeader`

- **Verdict: FAIL** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3` (sha256 `38bd108c0284`)
- Tolerance version: `1` (sha256 `1a8ebb6c4c57`)
- Collections: `invoiceHeader`
- Seed: `1`
- Generated: 2026-10-07T09:38:24.308142+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | FAIL (1 findings) |

## Tier 1 coverage
```json
{
  "source_counts": {
    "invoiceHeader": 1000
  }
}
```

## Tier 1 findings (1)
- `invoiceHeader` embed_cardinality: rows(INVOICE_LINE)=1500 vs sum(len(lines))=1463
