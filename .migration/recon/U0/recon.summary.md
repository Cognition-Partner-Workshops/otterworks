# Recon summary: `U0` - **FAIL**

- Mode: `live`
- Mapping `v1.0` / tolerances `v1` / seed `714559852` / params `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-01T21:26:38.025245+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 3 | PASS |
| 2 per_field_aggregates | 14 | PASS |
| 3 keyed_diffs | 136 | FAIL (64) |

Top findings (5 of 64; full list in result.json):
- T3 `codes` missing_doc: key=('CUST_STATUS', 1)
- T3 `codes` missing_doc: key=('CUST_STATUS', 2)
- T3 `codes` missing_doc: key=('CUST_STATUS', 3)
- T3 `codes` missing_doc: key=('CUST_STATUS', 99)
- T3 `codes` missing_doc: key=('CUST_TYPE', 1)

Full evidence: result.json, report.md (linked from the PR, not pasted).
