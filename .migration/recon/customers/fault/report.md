# Recon report: unit `customers`

- **Verdict: FAIL** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-22T21:07:58.128105+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 4 | FAIL (1 findings) |

## Tier 1 coverage
```json
{
  "source_counts": {
    "customers": 201,
    "customerVersions": 60,
    "entityAttrValue": 50
  }
}
```

## Tier 1 findings (1)
- `customers` embed_cardinality: rows(ENTITY_ATTR_VALUE)=555 vs sum(len(attributes))=554
