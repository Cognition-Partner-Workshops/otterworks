# Recon report: unit `dunning-ops`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-22T21:29:28.391199+00:00
- 8 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 5 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 3 | PASS |
| 2 | per_field_aggregates | 6 | PASS |
| 3 | keyed_diffs | 97 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "dunningAttempts": 61,
    "notifications": 21,
    "billingAuditLog": 15
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "dunningAttempts.tenantId",
    "dunningAttempts.invoiceId",
    "dunningAttempts.scheduledFor",
    "notifications.tenantId",
    "notifications.sentAt",
    "billingAuditLog.loggedAt",
    "billingAuditLog.module",
    "billingAuditLog.message"
  ],
  "string_aggregates_deferred_to_tier3": [
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
      "field": "billingAuditLog.module",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "billingAuditLog.message",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 5
}
```

## Tier 3 coverage
```json
{
  "dunningAttempts": {
    "mode": "full_diff",
    "population": 61,
    "duplicate_source_key_count": 0
  },
  "notifications": {
    "mode": "full_diff",
    "population": 21,
    "duplicate_source_key_count": 0
  },
  "billingAuditLog": {
    "mode": "full_diff",
    "population": 15,
    "duplicate_source_key_count": 0
  }
}
```
