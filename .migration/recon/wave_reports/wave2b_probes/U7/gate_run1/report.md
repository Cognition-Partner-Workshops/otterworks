# Recon report: unit `U7`

- **Verdict: FAIL**
- Mode: `live`
- Mapping version: `v1.0.1`
- Tolerance version: `v1`
- Seed: `714559852` | Params: `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-02T01:56:55.241768+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 5 | FAIL (2 findings) |

## Tier 1 findings (2)
- `replay_u7_rating_periods` root_count: rows(RATING_PERIODS)=3 vs docs=4
- `replay_u7_rating_periods` embed_cardinality: rows(RATING_RESULTS)=3 vs sum(len(results))=4
