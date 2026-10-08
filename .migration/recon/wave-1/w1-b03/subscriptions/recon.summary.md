# Recon summary: `subscriptions` - **FAIL**

- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-v3` / tolerances `tol-1` / seed `0`
- Generated: 2026-10-08T13:34:28.985878+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 5 | PASS |
| 2 per_field_aggregates | 4 | PASS |
| 3 keyed_diffs | 46 | FAIL (12) |

Top findings (5 of 12; full list in result.json):
- T3 `subscriptionsHist` field_diff: field HIST_DT->histDt key=tuple:28cb03b06c28
- T3 `subscriptionsHist` field_diff: field HIST_DT->histDtRaw key=tuple:28cb03b06c28
- T3 `subscriptionsHist` field_diff: field HIST_DT->histDt key=tuple:0555debc8a65
- T3 `subscriptionsHist` field_diff: field HIST_DT->histDtRaw key=tuple:0555debc8a65
- T3 `subscriptionsHist` field_diff: field HIST_DT->histDt key=tuple:4079e4af87d7

Full evidence: result.json, report.md (linked from the PR, not pasted).
