# Recon report: unit `U3`

- **Verdict: PASS**
- Mode: `live`
- Mapping version: `v1.0.1`
- Tolerance version: `v1`
- Seed: `714559852` | Params: `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-02T05:42:24.136540+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 3 | PASS |
| 2 | per_field_aggregates | 18 | PASS |
| 3 | keyed_diffs | 16260 | PASS |

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "documents.folder_id",
    "document_snapshots.label"
  ]
}
```

## Tier 3 coverage
```json
{
  "documents": {
    "mode": "full_diff",
    "population": 2000
  },
  "embeds_graded": {
    "documents.versions": 13876
  },
  "document_snapshots": {
    "mode": "full_diff",
    "population": 384
  }
}
```
