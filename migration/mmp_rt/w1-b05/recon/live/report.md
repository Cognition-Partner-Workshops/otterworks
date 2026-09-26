# Recon report: unit `w1-b05`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-v1`
- Tolerance version: `tol-v1`
- Seed: `1`
- Generated: 2026-09-26T17:38:07.401591+00:00
- 3 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 2 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 6 | PASS |
| 3 | keyed_diffs | 20000 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "audit_events": 20000
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
    "population": 20000,
    "duplicate_source_key_count": 0
  }
}
```
