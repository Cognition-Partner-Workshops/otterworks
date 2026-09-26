# Recon report: unit `w1-b01`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-v1-w1-b01-fixture`
- Tolerance version: `tol-v1`
- Seed: `1`
- Generated: 2026-09-26T17:55:13.115240+00:00
- 8 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 5 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 9 | PASS |
| 3 | keyed_diffs | 80 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "users": 50,
    "folders": 30
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "users.email",
    "users.displayName",
    "users.role",
    "users.createdAt",
    "folders.name",
    "folders.path",
    "folders.parentId",
    "folders.createdAt"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "users.email",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "users.displayName",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "users.role",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "folders.name",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "folders.path",
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
  "users": {
    "mode": "full_diff",
    "population": 50,
    "duplicate_source_key_count": 0
  },
  "folders": {
    "mode": "full_diff",
    "population": 30,
    "duplicate_source_key_count": 0
  }
}
```
