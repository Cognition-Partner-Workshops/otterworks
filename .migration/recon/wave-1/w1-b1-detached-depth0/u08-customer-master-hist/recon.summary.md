# Recon summary: `u08-customer-master-hist` - **UNVERIFIED**

- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-v1.1` / tolerances `tol-1` / seed `0`
- Generated: 2026-10-07T20:18:34.977499+00:00
- **WARNING: UNVERIFIED collection customerMasterHist: 0 source rows, key/shape/field rules unexercised**

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 2 | PASS |
| 2 per_field_aggregates | 21 | PASS |
| 3 keyed_diffs | 0 | PASS |
| 4 app_level_parity | 2 | PASS |

Full evidence: result.json, report.md (linked from the PR, not pasted).
