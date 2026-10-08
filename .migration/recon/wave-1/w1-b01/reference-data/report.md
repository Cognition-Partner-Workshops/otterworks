# Recon report: unit `reference-data`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-v3` (sha256 `c158f8bb469d`)
- Tolerance version: `tol-1` (sha256 `a23d517a8e6d`)
- Collections: `codes`, `tenants`, `plans`
- Seed: `0`
- Generated: 2026-10-08T13:33:02.515301+00:00
- 7 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 3 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 6 | PASS |
| 2 | per_field_aggregates | 7 | PASS |
| 3 | keyed_diffs | 50 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "codes": 32,
    "tenants": 15,
    "plans": 3
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "codes.codeDesc",
    "tenants.name",
    "tenants.taxExempt",
    "plans.code",
    "plans.monthlyFee",
    "plans.overageRate",
    "plans.active"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "codes.codeDesc",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "tenants.name",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "plans.code",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 3
}
```

## Tier 3 coverage
```json
{
  "codes": {
    "mode": "full_diff",
    "population": 32,
    "duplicate_source_key_count": 0
  },
  "tenants": {
    "mode": "full_diff",
    "population": 15,
    "duplicate_source_key_count": 0
  },
  "plans": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  }
}
```
