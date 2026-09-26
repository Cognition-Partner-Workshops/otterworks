# Recon summary: `u-06-invoice-header-bulk` - **PASS**

- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging) | Target: `local` (local target: NOT a merge verdict)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-draft-2` / tolerances `tol-1` / seed `1`
- Generated: 2026-09-26T18:17:01.419934+00:00
- **WARNING: embed invoiceHeader.lines: scoped by a where-predicate; extra target elements not checked**

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 2 | PASS |
| 2 per_field_aggregates | 2 | PASS |
| 3 keyed_diffs | 168713 | PASS |
| 4 app_level_parity | 3 | PASS |

Full evidence: result.json, report.md (linked from the PR, not pasted).
