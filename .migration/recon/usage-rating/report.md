# Recon report: unit `usage-rating`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-22T21:25:33.399166+00:00
- 5 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 2 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 3 | PASS |
| 2 | per_field_aggregates | 5 | PASS |
| 3 | keyed_diffs | 229 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "usageEvents": 133,
    "ratingPeriods": 33
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "usageEvents.tenantId",
    "usageEvents.occurredAt",
    "ratingPeriods.tenantId",
    "ratingPeriods.periodStart",
    "ratingPeriods.periodEnd"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "usageEvents.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "ratingPeriods.tenantId",
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
  "usageEvents": {
    "mode": "full_diff",
    "population": 133,
    "duplicate_source_key_count": 0
  },
  "ratingPeriods": {
    "mode": "full_diff",
    "population": 33,
    "duplicate_source_key_count": 0
  },
  "embeds_graded": {
    "ratingPeriods.results": 63
  }
}
```
