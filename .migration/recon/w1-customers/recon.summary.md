# Recon summary: `w1-customers` - **PASS**

- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-1` / tolerances `tol-1` / seed `1`
- Generated: 2026-09-18T21:52:30.173477+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 3 | PASS |
| 2 per_field_aggregates | 317 | PASS |
| 3 keyed_diffs | 33333 | PASS |
| 4 app_level_parity | 4 | PASS |

Full evidence: result.json, report.md (linked from the PR, not pasted).

live recon: not run, no source access. merge_eligible=false, reason: fixture evidence.
