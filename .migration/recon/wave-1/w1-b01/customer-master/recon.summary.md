# Recon summary: `customer-master` - **PASS**

- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-v3` / tolerances `tol-1` / seed `0`
- Generated: 2026-10-08T13:34:07.490902+00:00
- **WARNING: UNVERIFIED collection customerMasterHist: 0 source rows, key/shape/field rules unexercised**

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 2 | PASS |
| 2 per_field_aggregates | 32 | PASS |
| 3 keyed_diffs | 201 | PASS |

Full evidence: result.json, report.md (linked from the PR, not pasted).
