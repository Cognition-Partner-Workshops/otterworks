# Recon report: unit `plans`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `v2` (sha256 `6567c33adead`)
- Tolerance version: `tol-v1` (sha256 `829cbb4d2de0`)
- Collections: `plans`, `subscriptions`, `tenants`
- Seed: `1`
- Generated: 2026-10-15T00:02:58.570651+00:00
- 10 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 5 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 12 | PASS |
| 2 | per_field_aggregates | 13 | PASS |
| 3 | keyed_diffs | 26 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "plans": 3,
    "subscriptions": 9,
    "tenants": 9
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "plans.code",
    "plans.tier",
    "plans.active",
    "subscriptions.startsOn",
    "subscriptions.endsOn",
    "subscriptions.status",
    "subscriptions.suspendedOn",
    "tenants.name",
    "tenants.taxExempt",
    "tenants.status"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "plans.code",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "plans.tier",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "subscriptions.status",
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
      "field": "tenants.status",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 2
}
```

## Tier 3 coverage
```json
{
  "plans": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  },
  "subscriptions": {
    "mode": "full_diff",
    "population": 9,
    "duplicate_source_key_count": 0
  },
  "tenants": {
    "mode": "full_diff",
    "population": 9,
    "duplicate_source_key_count": 0
  },
  "embeds_graded": {
    "tenants.creditNotes": 5
  }
}
```
