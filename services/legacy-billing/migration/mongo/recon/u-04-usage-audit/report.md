# Recon report: unit `u-04-usage-audit`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging) | Target: `local` (local target: NOT a merge verdict)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-2`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-26T17:58:07.882939+00:00
- 5 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 3 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 4 | PASS |
| 3 | keyed_diffs | 817 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "usageEvents": 817,
    "billingAuditLog": 0
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "usageEvents.tenantId",
    "usageEvents.occurredAt",
    "billingAuditLog.loggedAt",
    "billingAuditLog.module",
    "billingAuditLog.message"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "usageEvents.tenantId",
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
  "fields_fully_deferred": 3
}
```

## Tier 3 coverage
```json
{
  "usageEvents": {
    "mode": "full_diff",
    "population": 817,
    "duplicate_source_key_count": 0
  },
  "billingAuditLog": {
    "mode": "full_diff",
    "population": 0,
    "duplicate_source_key_count": 0
  }
}
```
