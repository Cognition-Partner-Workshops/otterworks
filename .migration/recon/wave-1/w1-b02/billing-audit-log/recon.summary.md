# Recon summary: `billing-audit-log` - **FAIL**

- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-v3` / tolerances `tol-1` / seed `0`
- Generated: 2026-10-08T13:34:20.242758+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 1 | PASS |
| 2 per_field_aggregates | 1 | FAIL (2) |
| 3 keyed_diffs | 37 | FAIL (37) |

Top findings (5 of 39; full list in result.json):
- T2 `billingAuditLog` aggregate_min: field LOGGED_AT->loggedAt
- T2 `billingAuditLog` aggregate_max: field LOGGED_AT->loggedAt
- T3 `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:28cb03b06c28
- T3 `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:0555debc8a65
- T3 `billingAuditLog` field_diff: field LOGGED_AT->loggedAt key=tuple:4079e4af87d7

Full evidence: result.json, report.md (linked from the PR, not pasted).
