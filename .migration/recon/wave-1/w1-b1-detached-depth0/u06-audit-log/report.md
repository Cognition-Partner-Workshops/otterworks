# Recon report: unit `u06-audit-log`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-v1.1` (sha256 `3dc4060d3a4b`)
- Tolerance version: `tol-1` (sha256 `a23d517a8e6d`)
- Collections: `billingAuditLog`
- Seed: `0`
- Generated: 2026-10-07T20:17:25.225852+00:00
- 3 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 2 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 1 | PASS |
| 3 | keyed_diffs | 73 | PASS |
| 4 | app_level_parity | 2 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "billingAuditLog": 73
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
    "population": 73,
    "duplicate_source_key_count": 0
  }
}
```
