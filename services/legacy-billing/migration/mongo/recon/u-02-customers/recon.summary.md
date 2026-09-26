# Recon summary: `u-02-customers` - **FAIL**

- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging) | Target: `local` (local target: NOT a merge verdict)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-draft-2` / tolerances `tol-2` / seed `1`
- Generated: 2026-09-26T18:16:00.109017+00:00
- **WARNING: embed customerMaster.attributes: scoped by a where-predicate; extra target elements not checked**

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 3 | PASS |
| 2 per_field_aggregates | 30 | PASS |
| 3 keyed_diffs | 33338 | FAIL (63) |

Top findings (5 of 63; full list in result.json):
- T3 `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:d557c1a68d55
- T3 `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:38f32a47f070
- T3 `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:8a13998e6893
- T3 `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:3520d8e318e8
- T3 `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:44d669717b34

Full evidence: result.json, report.md (linked from the PR, not pasted).
