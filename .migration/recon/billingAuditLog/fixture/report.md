# Recon report: unit `billingAuditLog`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-2` (sha256 `232efbd7d88b`)
- Tolerance version: `1` (sha256 `1a8ebb6c4c57`)
- Collections: `billingAuditLog`
- Seed: `1`
- Generated: 2026-10-07T08:53:23.235642+00:00
- 3 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 2 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 1 | PASS |
| 3 | keyed_diffs | 0 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "billingAuditLog": 0
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "billingAuditLog.loggedAt",
    "billingAuditLog.module",
    "billingAuditLog.message"
  ],
  "string_aggregates_deferred_to_tier3": [
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
  "fields_fully_deferred": 2
}
```

## Tier 3 coverage
```json
{
  "billingAuditLog": {
    "mode": "full_diff",
    "population": 0,
    "duplicate_source_key_count": 0
  }
}
```
