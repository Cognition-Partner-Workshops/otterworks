# Recon summary: `w1-b02` - **FAIL**

- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-v1` / tolerances `tol-v1` / seed `1`
- Generated: 2026-09-26T17:35:30.259582+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 6 | FAIL (3) |

Top findings (3 of 3; full list in result.json):
- T1 `users` root_count: rows(users)=500 vs docs=50
- T1 `folders` root_count: rows(folders)=300 vs docs=30
- T1 `audit_events` root_count: rows(audit_events)=20000 vs docs=0

Full evidence: result.json, report.md (linked from the PR, not pasted).
