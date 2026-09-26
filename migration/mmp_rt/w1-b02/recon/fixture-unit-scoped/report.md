# Recon report: unit `w1-b02`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-v1-fixture-w1-b02-scoped`
- Tolerance version: `tol-v1`
- Seed: `1`
- Generated: 2026-09-26T17:30:04.236851+00:00
- 5 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 2 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 9 | PASS |
| 3 | keyed_diffs | 500 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "documents": 500
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "documents.title",
    "documents.folderId",
    "documents.status",
    "documents.createdAt",
    "documents.updatedAt"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "documents.title",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "documents.status",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 1
}
```

## Tier 3 coverage
```json
{
  "documents": {
    "mode": "full_diff",
    "population": 500,
    "duplicate_source_key_count": 0
  }
}
```
