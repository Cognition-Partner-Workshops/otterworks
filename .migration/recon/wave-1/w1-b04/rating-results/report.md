# Recon report: unit `rating-results`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-v3` (sha256 `c158f8bb469d`)
- Tolerance version: `tol-1` (sha256 `a23d517a8e6d`)
- Collections: `ratingResults`
- Seed: `0`
- Generated: 2026-10-08T13:20:13.227569+00:00
- 4 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 2 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 6 | PASS |
| 3 | keyed_diffs | 8 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "ratingResults": 8
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
    "population": 8,
    "duplicate_source_key_count": 0
  }
}
```
