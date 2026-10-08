# Recon report: unit `usage-events`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-v2` (sha256 `ccd1078bedc9`)
- Tolerance version: `tol-1` (sha256 `a23d517a8e6d`)
- Collections: `usageEvents`
- Seed: `0`
- Generated: 2026-10-08T13:07:08.251855+00:00
- 2 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 1 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 3 | PASS |
| 3 | keyed_diffs | 103 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "usageEvents": 103
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "usageEvents.tenantId",
    "usageEvents.occurredAt"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "usageEvents.tenantId",
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
  "usageEvents": {
    "mode": "full_diff",
    "population": 103,
    "duplicate_source_key_count": 0
  }
}
```
