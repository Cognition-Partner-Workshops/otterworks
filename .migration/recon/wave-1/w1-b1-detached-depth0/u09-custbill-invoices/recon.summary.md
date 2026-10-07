# Recon summary: `u09-custbill-invoices` - **PASS**

- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping `map-v1.1` / tolerances `tol-1` / seed `0`
- Generated: 2026-10-07T20:18:43.888858+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 2 | PASS |
| 2 per_field_aggregates | 8 | PASS |
| 3 keyed_diffs | 2500 | PASS |
| 4 app_level_parity | 3 | PASS |

Full evidence: result.json, report.md (linked from the PR, not pasted).
