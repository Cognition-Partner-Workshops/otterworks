# Recon summary: `U7` - **FAIL**

- Mode: `live`
- Mapping `v1.0.1` / tolerances `v1` / seed `714559852` / params `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-02T01:56:55.241768+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 5 | FAIL (2) |

Top findings (2 of 2; full list in result.json):
- T1 `replay_u7_rating_periods` root_count: rows(RATING_PERIODS)=3 vs docs=4
- T1 `replay_u7_rating_periods` embed_cardinality: rows(RATING_RESULTS)=3 vs sum(len(results))=4

Full evidence: result.json, report.md (linked from the PR, not pasted).
