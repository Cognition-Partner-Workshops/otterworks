# Recon report: unit `u-07-plsql-util`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging) | Target: `local` (local target: NOT a merge verdict)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-2`
- Tolerance version: `tol-2`
- Seed: `1`
- Generated: 2026-09-26T18:35:10.709074+00:00
- 4 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 3 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 1 | PASS |
| 3 | keyed_diffs | 32 | PASS |
| 4 | app_level_parity | 2 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "codes": 32,
    "billingAuditLog": 0
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "codes.codeDesc",
    "billingAuditLog.loggedAt",
    "billingAuditLog.module",
    "billingAuditLog.message"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "codes.codeDesc",
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
  "codes": {
    "mode": "full_diff",
    "population": 32,
    "duplicate_source_key_count": 0
  },
  "billingAuditLog": {
    "mode": "full_diff",
    "population": 0,
    "duplicate_source_key_count": 0
  }
}
```
