# Recon report: unit `w1-b03`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-v1-fixture`
- Tolerance version: `tol-v1`
- Seed: `1`
- Generated: 2026-09-26T17:29:25.247051+00:00
- 3 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 1 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 4 | PASS |
| 3 | keyed_diffs | 1200 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "comments": 1200
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "comments.body",
    "comments.createdAt",
    "comments.editedAt"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "comments.body",
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
  "comments": {
    "mode": "full_diff",
    "population": 1200,
    "duplicate_source_key_count": 0
  }
}
```
