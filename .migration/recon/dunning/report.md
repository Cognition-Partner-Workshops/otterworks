# Recon report: unit `dunning`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `v2` (sha256 `6567c33adead`)
- Tolerance version: `tol-v1` (sha256 `829cbb4d2de0`)
- Collections: `notifications`
- Seed: `1`
- Generated: 2026-10-15T01:32:21.281155+00:00
- 2 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 1 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 3 | PASS |
| 3 | keyed_diffs | 1 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "notifications": 1
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "notifications.kind",
    "notifications.sentAt"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "notifications.kind",
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
  "notifications": {
    "mode": "full_diff",
    "population": 1,
    "duplicate_source_key_count": 0
  }
}
```
