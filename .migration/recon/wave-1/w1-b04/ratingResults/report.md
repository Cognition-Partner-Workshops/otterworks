# Recon report: unit `ratingResults`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-draft-4` (sha256 `f5f8df83ed10`)
- Tolerance version: `1` (sha256 `1a8ebb6c4c57`)
- Collections: `ratingResults`
- Seed: `1`
- Generated: 2026-10-07T10:40:09.400169+00:00
- 4 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 2 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 6 | PASS |
| 3 | keyed_diffs | 3 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "ratingResults": 3
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "ratingResults.periodId",
    "ratingResults.subscriptionId",
    "ratingResults.overageAmount",
    "ratingResults.createdAt"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "ratingResults.periodId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "ratingResults.subscriptionId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 2
}
```

## Tier 3 coverage
```json
{
  "ratingResults": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  }
}
```
