# Recon summary: `invoiceHeader` - **PASS**

- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-draft-4` / tolerances `1` / seed `1`
- Generated: 2026-10-07T10:01:54.913528+00:00
- **WARNING: embed invoiceHeader.lines: scoped by a where-predicate; extra target elements not checked**

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 2 | PASS |
| 2 per_field_aggregates | 2 | PASS |
| 3 keyed_diffs | 2463 | PASS |

Full evidence: result.json, report.md (linked from the PR, not pasted).
