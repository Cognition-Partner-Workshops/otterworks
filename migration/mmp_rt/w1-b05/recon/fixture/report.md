# Recon report: unit `w1-b05`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-v1-fixture`
- Tolerance version: `tol-v1`
- Seed: `1`
- Generated: 2026-09-26T17:36:44.681999+00:00
- 3 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 2 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 6 | PASS |
| 3 | keyed_diffs | 2000 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "audit_events": 2000
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "audit_events.action",
    "audit_events.targetType",
    "audit_events.ts"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "audit_events.action",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "audit_events.targetType",
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
  "audit_events": {
    "mode": "full_diff",
    "population": 2000,
    "duplicate_source_key_count": 0
  }
}
```
