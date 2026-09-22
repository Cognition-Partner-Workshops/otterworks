# Recon summary: `codes` - **FAIL**

- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-draft-3` / tolerances `tol-1` / seed `1`
- Generated: 2026-09-22T20:47:31.303656+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 1 | PASS |
| 2 per_field_aggregates | 0 | PASS |
| 3 keyed_diffs | 42 | FAIL (2) |

Top findings (2 of 2; full list in result.json):
- T3 `codes` missing_doc: missing document key=tuple:2f06660fde32
- T3 `codes` extra_doc: extra document key=tuple:73f0fad491ac

Full evidence: result.json, report.md (linked from the PR, not pasted).
