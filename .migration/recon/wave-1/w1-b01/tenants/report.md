# Recon report: unit `tenants`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-draft-4` (sha256 `f5f8df83ed10`)
- Tolerance version: `1` (sha256 `1a8ebb6c4c57`)
- Collections: `tenants`
- Seed: `1`
- Generated: 2026-10-07T10:38:37.681789+00:00
- 2 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 1 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 2 | PASS |
| 3 | keyed_diffs | 15 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "tenants": 15
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "tenants.name",
    "tenants.taxExempt"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "tenants.name",
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
  "tenants": {
    "mode": "full_diff",
    "population": 15,
    "duplicate_source_key_count": 0
  }
}
```
