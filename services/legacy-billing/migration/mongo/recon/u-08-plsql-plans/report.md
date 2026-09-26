# Recon report: unit `u-08-plsql-plans`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging) | Target: `local` (local target: NOT a merge verdict)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-2`
- Tolerance version: `tol-2`
- Seed: `1`
- Generated: 2026-09-26T18:36:58.899763+00:00
- 20 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 8 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 4 | PASS |
| 2 | per_field_aggregates | 10 | PASS |
| 3 | keyed_diffs | 143 | PASS |
| 4 | app_level_parity | 4 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "tenants": 70,
    "plans": 3,
    "subscriptions": 70,
    "subscriptionsHist": 0
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
    "subscriptionsHist.histDt",
    "subscriptionsHist.histOp",
    "subscriptionsHist.id",
    "subscriptionsHist.tenantId",
    "subscriptionsHist.planId",
    "subscriptionsHist.startsOn",
    "subscriptionsHist.endsOn",
    "subscriptionsHist.statusCd",
    "subscriptionsHist.suspendedOn"
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
      "field": "subscriptionsHist.histOp",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "subscriptionsHist.id",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "subscriptionsHist.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "subscriptionsHist.planId",
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
    "population": 70,
    "duplicate_source_key_count": 0
  },
  "plans": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  },
  "subscriptions": {
    "mode": "full_diff",
    "population": 70,
    "duplicate_source_key_count": 0
  },
  "subscriptionsHist": {
    "mode": "full_diff",
    "population": 0,
    "duplicate_source_key_count": 0
  }
}
```
