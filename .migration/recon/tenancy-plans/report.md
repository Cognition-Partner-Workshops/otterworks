# Recon report: unit `tenancy-plans`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-22T21:00:24.944601+00:00
- 20 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 8 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 4 | PASS |
| 2 | per_field_aggregates | 10 | PASS |
| 3 | keyed_diffs | 46 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "tenants": 13,
    "plans": 6,
    "subscriptions": 15,
    "subscriptionVersions": 12
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "tenants.name",
    "tenants.taxExempt",
    "plans.code",
    "plans.monthlyFee",
    "plans.overageRate",
    "plans.active",
    "subscriptions.tenantId",
    "subscriptions.planId",
    "subscriptions.startsOn",
    "subscriptions.endsOn",
    "subscriptions.suspendedOn",
    "subscriptionVersions.histDt",
    "subscriptionVersions.histOp",
    "subscriptionVersions.id",
    "subscriptionVersions.tenantId",
    "subscriptionVersions.planId",
    "subscriptionVersions.startsOn",
    "subscriptionVersions.endsOn",
    "subscriptionVersions.statusCd",
    "subscriptionVersions.suspendedOn"
  ],
  "string_aggregates_deferred_to_tier3": [
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
    },
    {
      "field": "subscriptions.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "subscriptions.planId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "subscriptionVersions.histOp",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "subscriptionVersions.id",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "subscriptionVersions.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "subscriptionVersions.planId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 14
}
```

## Tier 3 coverage
```json
{
  "tenants": {
    "mode": "full_diff",
    "population": 13,
    "duplicate_source_key_count": 0
  },
  "plans": {
    "mode": "full_diff",
    "population": 6,
    "duplicate_source_key_count": 0
  },
  "subscriptions": {
    "mode": "full_diff",
    "population": 15,
    "duplicate_source_key_count": 0
  },
  "subscriptionVersions": {
    "mode": "full_diff",
    "population": 12,
    "duplicate_source_key_count": 0
  }
}
```
