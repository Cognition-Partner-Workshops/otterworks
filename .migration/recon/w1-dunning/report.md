# Recon report: unit `w1-dunning`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-1`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-18T22:17:00.864233+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 3 | PASS |
| 2 | per_field_aggregates | 11 | PASS |
| 3 | keyed_diffs | 2 | PASS |
| 4 | app_level_parity | 4 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "dunningAttempts": 1,
    "notifications": 1,
    "billingAuditLog": 0
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "dunningAttempts.tenantId",
    "dunningAttempts.invoiceId",
    "notifications.tenantId",
    "billingAuditLog.module",
    "billingAuditLog.message"
  ]
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
  },
  "billingAuditLog": {
    "mode": "full_diff",
    "population": 0,
    "duplicate_source_key_count": 0
  }
}
```
