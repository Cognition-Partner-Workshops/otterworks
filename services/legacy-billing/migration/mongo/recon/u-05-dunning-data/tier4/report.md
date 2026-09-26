# Recon report: unit `u-05-dunning-data`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging) | Target: `local` (local target: NOT a merge verdict)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-2`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-26T17:56:32.945737+00:00
- 5 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 3 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 5 | PASS |
| 3 | keyed_diffs | 2 | PASS |
| 4 | app_level_parity | 1 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "dunningAttempts": 1,
    "notifications": 1
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
    "notifications.sentAt"
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
    }
  ],
  "fields_fully_deferred": 3
}
```

## Tier 3 coverage
```json
{
  "dunningAttempts": {
    "mode": "full_diff",
    "population": 1,
    "duplicate_source_key_count": 0
  },
  "notifications": {
    "mode": "full_diff",
    "population": 1,
    "duplicate_source_key_count": 0
  }
}
```
