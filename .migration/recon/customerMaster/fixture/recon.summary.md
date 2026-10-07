# Recon summary: `customerMaster` - **FAIL**

- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-draft-2` / tolerances `1` / seed `1`
- Generated: 2026-10-07T08:53:21.392553+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 2 | PASS |
| 2 per_field_aggregates | 15 | PASS |
| 3 keyed_diffs | 271 | FAIL (44) |

Top findings (5 of 44; full list in result.json):
- T3 `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:5612bc348b8f
- T3 `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:fc0a77a9f9da
- T3 `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:bb6e05db9415
- T3 `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:ce269a7125e3
- T3 `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:ec75aafa8388

Full evidence: result.json, report.md (linked from the PR, not pasted).
