# Recon report: unit `plans`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-4` (sha256 `f5f8df83ed10`)
- Tolerance version: `1` (sha256 `1a8ebb6c4c57`)
- Collections: `plans`
- Seed: `1`
- Generated: 2026-10-07T11:00:59.382459+00:00
- 4 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 1 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 5 | PASS |
| 3 | keyed_diffs | 3 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "plans": 3
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "plans.code",
    "plans.monthlyFee",
    "plans.overageRate",
    "plans.active"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "plans.code",
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
  "plans": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  }
}
```
