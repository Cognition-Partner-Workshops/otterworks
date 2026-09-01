# Recon report: unit `usage_rating`

- **Verdict: PASS**
- Mode: `live`
- Mapping version: `m1`
- Tolerance version: `v1`
- Seed: `20260901` | Params: `{'batch_no': '85559852'}`
- Generated: 2026-09-01T05:14:03.777907+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 3 | PASS |
| 2 | per_field_aggregates | 9 | PASS |
| 3 | keyed_diffs | 820 | PASS |

## Tier 3 coverage
```json
{
  "usage_events": {
    "mode": "full_diff",
    "population": 814
  },
  "rating_periods": {
    "mode": "full_diff",
    "population": 3
  },
  "embeds_graded": {
    "rating_periods.results": 3
  }
}
```
