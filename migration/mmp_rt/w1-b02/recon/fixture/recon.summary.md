# Recon summary: `w1-b02` - **FAIL**

- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-v1-fixture` / tolerances `tol-v1` / seed `1`
- Generated: 2026-09-26T17:28:30.467239+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 6 | FAIL (2) |

Top findings (2 of 2; full list in result.json):
- T1 `shares` root_count: rows(fx_src_shares)=300 vs docs=0
- T1 `audit_events` root_count: rows(fx_src_audit_events)=2000 vs docs=0

Full evidence: result.json, report.md (linked from the PR, not pasted).
