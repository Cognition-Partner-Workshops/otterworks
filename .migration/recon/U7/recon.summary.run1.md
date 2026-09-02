# Recon summary: `U7` - **FAIL**

- Mode: `live`
- Mapping `v1.0.1` / tolerances `v1` / seed `714559852` / params `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-02T01:11:04.632856+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 6 | FAIL (1) |

Top findings (1 of 1; full list in result.json):
- T1 `replay_u7_billing_audit_log` root_count: rows(BILLING_AUDIT_LOG)=0 vs docs=1

Full evidence: result.json, report.md (linked from the PR, not pasted).
