# Recon report: unit `parallel-run-cycle-3`

- **Verdict: PASS** (values redacted)
- Mode: `continuous`
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `v2` (sha256 `6567c33adead`)
- Tolerance version: `tol-v1` (sha256 `829cbb4d2de0`)
- Collections: `invoices`, `notifications`, `plans`, `ratingPeriods`, `subscriptions`, `tenants`, `usageEvents`
- Seed: `1`
- Generated: 2026-10-15T02:22:52.996098+00:00
- 18 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 8 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 24 | PASS |
| 2 | per_field_aggregates | 30 | PASS |
| 3 | keyed_diffs | 150 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "invoices": 12,
    "notifications": 2,
    "plans": 3,
    "ratingPeriods": 15,
    "subscriptions": 15,
    "tenants": 9,
    "usageEvents": 10
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "invoices.issuedAt",
    "invoices.status",
    "notifications.kind",
    "notifications.sentAt",
    "plans.code",
    "plans.tier",
    "plans.active",
    "ratingPeriods.periodStart",
    "ratingPeriods.periodEnd",
    "subscriptions.startsOn",
    "subscriptions.endsOn",
    "subscriptions.status",
    "subscriptions.suspendedOn",
    "tenants.name",
    "tenants.taxExempt",
    "tenants.status",
    "usageEvents.occurredAt",
    "usageEvents.kind"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "invoices.status",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "notifications.kind",
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
    },
    {
      "field": "usageEvents.kind",
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
  "invoices": {
    "mode": "stratified_sample",
    "population": 12,
    "sampled": 12,
    "coverage": 1.0,
    "duplicate_source_key_count": 0
  },
  "embeds_graded": {
    "invoices.invoiceLines": 47,
    "invoices.dunningAttempts": 17,
    "ratingPeriods.rating": 15,
    "tenants.creditNotes": 5
  },
  "notifications": {
    "mode": "stratified_sample",
    "population": 2,
    "sampled": 2,
    "coverage": 1.0,
    "duplicate_source_key_count": 0
  },
  "plans": {
    "mode": "stratified_sample",
    "population": 3,
    "sampled": 3,
    "coverage": 1.0,
    "duplicate_source_key_count": 0
  },
  "ratingPeriods": {
    "mode": "stratified_sample",
    "population": 15,
    "sampled": 15,
    "coverage": 1.0,
    "duplicate_source_key_count": 0
  },
  "subscriptions": {
    "mode": "stratified_sample",
    "population": 15,
    "sampled": 15,
    "coverage": 1.0,
    "duplicate_source_key_count": 0
  },
  "tenants": {
    "mode": "stratified_sample",
    "population": 9,
    "sampled": 9,
    "coverage": 1.0,
    "duplicate_source_key_count": 0
  },
  "usageEvents": {
    "mode": "stratified_sample",
    "population": 10,
    "sampled": 10,
    "coverage": 1.0,
    "duplicate_source_key_count": 0
  }
}
```
