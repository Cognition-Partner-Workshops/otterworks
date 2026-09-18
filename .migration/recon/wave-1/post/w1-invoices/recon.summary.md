# Recon summary: `w1-invoices` - **PASS**

- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-1` / tolerances `tol-1` / seed `1`
- Generated: 2026-09-18T22:37:17.414895+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 5 | PASS |
| 2 per_field_aggregates | 38 | PASS |
| 3 keyed_diffs | 19764 | PASS |
| 4 app_level_parity | 4 | PASS |

Full evidence: result.json, report.md (linked from the PR, not pasted).

live recon: not run, no source access. merge_eligible=false, reason: fixture evidence.
