# Recon report: unit `subscriptions`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3` (sha256 `38bd108c0284`)
- Tolerance version: `1` (sha256 `1a8ebb6c4c57`)
- Collections: `subscriptions`
- Seed: `1`
- Generated: 2026-10-07T09:25:55.459550+00:00
- 5 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 2 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 2 | PASS |
| 3 | keyed_diffs | 30 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "subscriptions": 15
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "subscriptions.tenantId",
    "subscriptions.planId",
    "subscriptions.startsOn",
    "subscriptions.endsOn",
    "subscriptions.suspendedOn"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "subscriptions.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "subscriptions.planId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 4
}
```

## Tier 3 coverage
```json
{
  "subscriptions": {
    "mode": "full_diff",
    "population": 15,
    "duplicate_source_key_count": 0
  }
}
```
