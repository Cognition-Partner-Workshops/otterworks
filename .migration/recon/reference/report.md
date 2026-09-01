# Recon report: unit `reference`

- **Verdict: PASS**
- Mode: `live`
- Mapping version: `m1`
- Tolerance version: `v1`
- Seed: `20260901` | Params: `{'batch_no': '85559852'}`
- Generated: 2026-09-01T04:16:49.356420+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 3 | PASS |
| 2 | per_field_aggregates | 14 | PASS |
| 3 | keyed_diffs | 104 | PASS |

## Tier 3 coverage
```json
{
  "codes": {
    "mode": "full_diff",
    "population": 32
  },
  "tenants": {
    "mode": "full_diff",
    "population": 69
  },
  "plans": {
    "mode": "full_diff",
    "population": 3
  }
}
```
