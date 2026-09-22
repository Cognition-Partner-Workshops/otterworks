# Recon summary: `customers` - **PASS**

- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-draft-3` / tolerances `tol-1` / seed `1`
- Generated: 2026-09-22T21:08:08.517065+00:00
- **WARNING: embed customers.attributes: scoped by a where-predicate; extra target elements not checked**

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 4 | PASS |
| 2 per_field_aggregates | 30 | PASS |
| 3 keyed_diffs | 865 | PASS |

Full evidence: result.json, report.md (linked from the PR, not pasted).
