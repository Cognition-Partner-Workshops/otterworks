# Recon report: unit `rating-periods`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-v3` (sha256 `c158f8bb469d`)
- Tolerance version: `tol-1` (sha256 `a23d517a8e6d`)
- Collections: `ratingPeriods`
- Seed: `0`
- Generated: 2026-10-08T13:34:22.321699+00:00
- 3 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 1 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 2 | PASS |
| 3 | keyed_diffs | 8 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "ratingPeriods": 8
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "ratingPeriods.tenantId",
    "ratingPeriods.periodStart",
    "ratingPeriods.periodEnd"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "ratingPeriods.tenantId",
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
  "ratingPeriods": {
    "mode": "full_diff",
    "population": 8,
    "duplicate_source_key_count": 0
  }
}
```
