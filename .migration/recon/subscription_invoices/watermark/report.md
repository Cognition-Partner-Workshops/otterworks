# Recon report: unit `subscription_invoices`

- **Verdict: PASS**
- Mode: `live`
- Mapping version: `m1`
- Tolerance version: `v1`
- Seed: `20260901` | Params: `{'batch_no': '85559852'}`
- Generated: 2026-09-01T05:14:06.360886+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 8 | PASS |
| 3 | keyed_diffs | 5 | PASS |

## Tier 3 coverage
```json
{
  "subscription_invoices": {
    "mode": "full_diff",
    "population": 3
  },
  "embeds_graded": {
    "subscription_invoices.lines": 2
  }
}
```
