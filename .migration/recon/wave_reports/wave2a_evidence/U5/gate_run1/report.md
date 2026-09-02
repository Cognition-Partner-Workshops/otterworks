# Recon report: unit `U5`

- **Verdict: FAIL**
- Mode: `live`
- Mapping version: `v1.0.1`
- Tolerance version: `v1`
- Seed: `714559852` | Params: `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-02T00:46:46.716276+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 11 | FAIL (1 findings) |

## Tier 1 findings (1)
- `billing_audit_log` root_count: rows(BILLING_AUDIT_LOG)=1 vs docs=0
