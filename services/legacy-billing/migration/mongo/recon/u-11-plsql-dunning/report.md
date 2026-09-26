# Recon report: unit `u-11-plsql-dunning`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging) | Target: `local` (local target: NOT a merge verdict)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3.1`
- Tolerance version: `tol-2`
- Seed: `1`
- Generated: 2026-09-26T18:48:47.811153+00:00
- 21 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 10 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 5 | PASS |
| 2 | per_field_aggregates | 10 | PASS |
| 3 | keyed_diffs | 142 | PASS |
| 4 | app_level_parity | 3 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "tenants": 70,
    "subscriptions": 70,
    "dunningAttempts": 1,
    "notifications": 1,
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
    "subscriptions.tenantId",
    "subscriptions.planId",
    "subscriptions.startsOn",
    "subscriptions.endsOn",
    "subscriptions.suspendedOn",
    "dunningAttempts.tenantId",
    "dunningAttempts.invoiceId",
    "dunningAttempts.scheduledFor",
    "notifications.tenantId",
    "notifications.sentAt",
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
      "field": "dunningAttempts.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "dunningAttempts.invoiceId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "notifications.tenantId",
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
  "fields_fully_deferred": 16
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
  "subscriptions": {
    "mode": "full_diff",
    "population": 70,
    "duplicate_source_key_count": 0
  },
  "dunningAttempts": {
    "mode": "full_diff",
    "population": 1,
    "duplicate_source_key_count": 0
  },
  "notifications": {
    "mode": "full_diff",
    "population": 1,
    "duplicate_source_key_count": 0
  },
  "subscriptionsHist": {
    "mode": "full_diff",
    "population": 0,
    "duplicate_source_key_count": 0
  }
}
```
