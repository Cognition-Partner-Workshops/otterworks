# Recon report: unit `notifications`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-v2` (sha256 `ccd1078bedc9`)
- Tolerance version: `tol-1` (sha256 `a23d517a8e6d`)
- Collections: `notifications`
- Seed: `0`
- Generated: 2026-10-08T13:07:10.346384+00:00
- 2 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 1 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 2 | PASS |
| 3 | keyed_diffs | 2 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "notifications": 2
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "notifications.tenantId",
    "notifications.sentAt"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "notifications.tenantId",
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
  "notifications": {
    "mode": "full_diff",
    "population": 2,
    "duplicate_source_key_count": 0
  }
}
```
