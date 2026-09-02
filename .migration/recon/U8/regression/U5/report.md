# Recon report: unit `U5`

- **Verdict: FAIL**
- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `v1.0.1`
- Tolerance version: `v1`
- Seed: `714559852`
- Generated: 2026-09-02T06:22:44.662204+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 11 | FAIL (1 findings) |

## Tier 1 coverage
```json
{
  "source_counts": {
    "SUBSCRIPTIONS": 69,
    "SUBSCRIPTIONS_HIST": 0,
    "USAGE_EVENTS": 814,
    "RATING_PERIODS": 3,
    "INVOICES": 3,
    "CREDIT_NOTES": 5,
    "DUNNING_ATTEMPTS": 1,
    "NOTIFICATIONS": 1,
    "BILLING_AUDIT_LOG": 0
  }
}
```

## Tier 1 findings (1)
- `billing_audit_log` root_count: rows(BILLING_AUDIT_LOG)=0 vs docs=1
