# Recon summary: `invoicing` - **FAIL**

- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-draft-3` / tolerances `tol-1` / seed `1`
- Generated: 2026-09-22T21:27:51.425386+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 3 | PASS |
| 2 per_field_aggregates | 8 | PASS |
| 3 keyed_diffs | 183 | FAIL (1) |

Top findings (1 of 1; full list in result.json):
- T3 `invoices` embed_field_diff: lines field AMOUNT->amount parent=tuple:8f274a40c02f key=tuple:28cb03b06c28

Full evidence: result.json, report.md (linked from the PR, not pasted).
