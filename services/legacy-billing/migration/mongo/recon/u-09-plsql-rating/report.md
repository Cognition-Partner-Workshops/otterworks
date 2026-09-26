# Recon report: unit `u-09-plsql-rating`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging) | Target: `local` (local target: NOT a merge verdict)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3.1`
- Tolerance version: `tol-2`
- Seed: `1`
- Generated: 2026-09-26T18:48:46.407795+00:00
- 7 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 3 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 8 | PASS |
| 3 | keyed_diffs | 6 | PASS |
| 4 | app_level_parity | 2 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "ratingPeriods": 3,
    "ratingResults": 3
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
    "population": 3,
    "duplicate_source_key_count": 0
  },
  "ratingResults": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  }
}
```
