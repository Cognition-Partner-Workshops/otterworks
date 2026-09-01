# Recon report: unit `U4`

- **Verdict: PASS**
- Mode: `live`
- Mapping version: `v1.0`
- Tolerance version: `v1`
- Seed: `714559852` | Params: `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-01T22:23:31.559824+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 12 | PASS |
| 3 | keyed_diffs | 10000 | PASS |

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "files.folder_id"
  ]
}
```

## Tier 3 coverage
```json
{
  "files": {
    "mode": "full_diff",
    "population": 10000
  }
}
```
