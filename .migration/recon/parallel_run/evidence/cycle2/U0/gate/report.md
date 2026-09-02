# Recon report: unit `U0`

- **Verdict: PASS**
- Mode: `live`
- Mapping version: `v1.0.1`
- Tolerance version: `v1`
- Seed: `714559852` | Params: `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-02T05:35:33.269811+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 3 | PASS |
| 2 | per_field_aggregates | 14 | PASS |
| 3 | keyed_diffs | 104 | PASS |

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "codes.code_type",
    "codes.code_desc",
    "tenants.id",
    "tenants.name",
    "tenants.tax_exempt_yn",
    "plans.id",
    "plans.code",
    "plans.active_yn"
  ]
}
```

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
