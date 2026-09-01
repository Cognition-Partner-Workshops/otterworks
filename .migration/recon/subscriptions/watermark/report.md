# Recon report: unit `subscriptions`

- **Verdict: PASS**
- Mode: `live`
- Mapping version: `m1`
- Tolerance version: `v1`
- Seed: `20260901` | Params: `{'batch_no': '85559852'}`
- Generated: 2026-09-01T05:13:36.243080+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 7 | PASS |
| 3 | keyed_diffs | 69 | PASS |

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "subscriptions.ends_on",
    "subscriptions.suspended_on"
  ]
}
```

## Tier 3 coverage
```json
{
  "subscriptions": {
    "mode": "full_diff",
    "population": 69
  },
  "embeds_graded": {
    "subscriptions.history": 0
  }
}
```
