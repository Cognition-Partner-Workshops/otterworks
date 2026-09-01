# Recon report: unit `collections_ops`

- **Verdict: PASS**
- Mode: `live`
- Mapping version: `m1`
- Tolerance version: `v1`
- Seed: `20260901` | Params: `{'batch_no': '85559852'}`
- Generated: 2026-09-01T05:14:10.569279+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 4 | PASS |
| 2 | per_field_aggregates | 19 | PASS |
| 3 | keyed_diffs | 7 | PASS |

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "billing_audit_log.module",
    "billing_audit_log.message"
  ]
}
```

## Tier 3 coverage
```json
{
  "credit_notes": {
    "mode": "full_diff",
    "population": 5
  },
  "dunning_attempts": {
    "mode": "full_diff",
    "population": 1
  },
  "notifications": {
    "mode": "full_diff",
    "population": 1
  },
  "billing_audit_log": {
    "mode": "full_diff",
    "population": 0
  }
}
```
