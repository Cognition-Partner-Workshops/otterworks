# Recon report: unit `w1-b04`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-v1`
- Tolerance version: `tol-v1`
- Seed: `1`
- Generated: 2026-09-26T17:32:53.545033+00:00
- 2 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 1 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 3 | PASS |
| 3 | keyed_diffs | 3000 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "shares": 3000
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "shares.permission",
    "shares.expiresAt"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "shares.permission",
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
  "shares": {
    "mode": "full_diff",
    "population": 3000,
    "duplicate_source_key_count": 0
  }
}
```
