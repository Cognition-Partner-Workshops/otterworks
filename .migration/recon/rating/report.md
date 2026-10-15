# Recon report: unit `rating`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `v2` (sha256 `6567c33adead`)
- Tolerance version: `tol-v1` (sha256 `829cbb4d2de0`)
- Collections: `ratingPeriods`, `usageEvents`
- Seed: `1`
- Generated: 2026-10-15T00:36:12.415630+00:00
- 4 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 1 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 5 | PASS |
| 2 | per_field_aggregates | 7 | PASS |
| 3 | keyed_diffs | 16 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "ratingPeriods": 3,
    "usageEvents": 10
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "ratingPeriods.periodStart",
    "ratingPeriods.periodEnd",
    "usageEvents.occurredAt",
    "usageEvents.kind"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "usageEvents.kind",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ]
}
```

## Tier 3 coverage
```json
{
  "ratingPeriods": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  },
  "embeds_graded": {
    "ratingPeriods.rating": 3
  },
  "usageEvents": {
    "mode": "full_diff",
    "population": 10,
    "duplicate_source_key_count": 0
  }
}
```
