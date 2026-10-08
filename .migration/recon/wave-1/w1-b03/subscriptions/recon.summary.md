# Recon summary: `subscriptions` - **FAIL**

- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-v2` / tolerances `tol-1` / seed `0`
- Generated: 2026-10-08T13:07:32.457182+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 5 | PASS |
| 2 per_field_aggregates | 3 | PASS |
| 3 keyed_diffs | 46 | FAIL (6) |

Top findings (5 of 6; full list in result.json):
- T3 `subscriptionsHist` field_diff: field HIST_DT->histDt key=tuple:28cb03b06c28
- T3 `subscriptionsHist` field_diff: field HIST_DT->histDt key=tuple:0555debc8a65
- T3 `subscriptionsHist` field_diff: field HIST_DT->histDt key=tuple:4079e4af87d7
- T3 `subscriptionsHist` field_diff: field HIST_DT->histDt key=tuple:3912a1d67a34
- T3 `subscriptionsHist` field_diff: field HIST_DT->histDt key=tuple:666aa17826ad

Full evidence: result.json, report.md (linked from the PR, not pasted).
