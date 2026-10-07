# Recon report: unit `u03-rating`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-v1.1` (sha256 `3dc4060d3a4b`)
- Tolerance version: `tol-1` (sha256 `a23d517a8e6d`)
- Collections: `ratingPeriods`, `ratingResults`
- Seed: `0`
- Generated: 2026-10-07T20:18:57.533727+00:00
- 7 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 3 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 4 | PASS |
| 2 | per_field_aggregates | 8 | PASS |
| 3 | keyed_diffs | 16 | PASS |
| 4 | app_level_parity | 3 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "ratingPeriods": 8,
    "ratingResults": 8
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "ratingPeriods.tenantId",
    "ratingPeriods.periodStart",
    "ratingPeriods.periodEnd",
    "ratingResults.periodId",
    "ratingResults.subscriptionId",
    "ratingResults.overageAmount",
    "ratingResults.createdAt"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "ratingPeriods.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
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
  "fields_fully_deferred": 3
}
```

## Tier 3 coverage
```json
{
  "ratingPeriods": {
    "mode": "full_diff",
    "population": 8,
    "duplicate_source_key_count": 0
  },
  "ratingResults": {
    "mode": "full_diff",
    "population": 8,
    "duplicate_source_key_count": 0
  }
}
```
