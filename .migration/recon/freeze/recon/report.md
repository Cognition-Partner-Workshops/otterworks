# Recon report: unit `freeze-watermark`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `v2` (sha256 `6567c33adead`)
- Tolerance version: `tol-v1` (sha256 `829cbb4d2de0`)
- Collections: `invoices`, `notifications`, `plans`, `ratingPeriods`, `subscriptions`, `tenants`, `usageEvents`
- Seed: `1`
- Generated: 2026-10-15T03:20:46.131516+00:00
- 18 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 8 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 24 | PASS |
| 2 | per_field_aggregates | 30 | PASS |
| 3 | keyed_diffs | 49 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "invoices": 3,
    "notifications": 1,
    "plans": 3,
    "ratingPeriods": 3,
    "subscriptions": 9,
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
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  },
  "embeds_graded": {
    "invoices.invoiceLines": 2,
    "invoices.dunningAttempts": 1,
    "ratingPeriods.rating": 3,
    "tenants.creditNotes": 5
  },
  "notifications": {
    "mode": "full_diff",
    "population": 1,
    "duplicate_source_key_count": 0
  },
  "plans": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  },
  "ratingPeriods": {
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
  "usageEvents": {
    "mode": "full_diff",
    "population": 10,
    "duplicate_source_key_count": 0
  }
}
```
