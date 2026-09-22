# Recon summary: `dunning-ops` - **FAIL**

- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-draft-3` / tolerances `tol-1` / seed `1`
- Generated: 2026-09-22T21:29:26.353191+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 3 | FAIL (1) |

Top findings (1 of 1; full list in result.json):
- T1 `billingAuditLog` root_count: rows(BILLING_AUDIT_LOG)=15 vs docs=14

Full evidence: result.json, report.md (linked from the PR, not pasted).
