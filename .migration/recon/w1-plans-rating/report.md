# Recon report: unit `w1-plans-rating`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-1`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-18T22:16:59.257324+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 8 | PASS |
| 2 | per_field_aggregates | 40 | PASS |
| 3 | keyed_diffs | 993 | PASS |
| 4 | app_level_parity | 5 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "codes": 32,
    "tenants": 69,
    "plans": 3,
    "subscriptions": 69,
    "usageEvents": 814,
    "ratingPeriods": 3,
    "ratingResults": 3,
    "subscriptionsHist": 0
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
    "plans.active",
    "subscriptions.tenantId",
    "subscriptions.planId",
    "subscriptions.endsOn",
    "subscriptions.suspendedOn",
    "usageEvents.tenantId",
    "ratingPeriods.tenantId",
    "ratingResults.periodId",
    "ratingResults.subscriptionId",
    "ratingResults.overageAmount",
    "subscriptionsHist.histDt",
    "subscriptionsHist.histOp",
    "subscriptionsHist.id",
    "subscriptionsHist.tenantId",
    "subscriptionsHist.planId",
    "subscriptionsHist.startsOn",
    "subscriptionsHist.endsOn",
    "subscriptionsHist.statusCd",
    "subscriptionsHist.suspendedOn"
  ]
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
    "population": 69,
    "duplicate_source_key_count": 0
  },
  "plans": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  },
  "subscriptions": {
    "mode": "full_diff",
    "population": 69,
    "duplicate_source_key_count": 0
  },
  "usageEvents": {
    "mode": "full_diff",
    "population": 814,
    "duplicate_source_key_count": 0
  },
  "ratingPeriods": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  },
  "ratingResults": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  },
  "subscriptionsHist": {
    "mode": "full_diff",
    "population": 0,
    "duplicate_source_key_count": 0
  }
}
```
