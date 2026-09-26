# Recon report: unit `w1-b03`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-v1`
- Tolerance version: `tol-v1`
- Seed: `1`
- Generated: 2026-09-26T17:30:08.662619+00:00
- 3 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 1 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 4 | PASS |
| 3 | keyed_diffs | 12000 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "comments": 12000
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
    "population": 12000,
    "duplicate_source_key_count": 0
  }
}
```
