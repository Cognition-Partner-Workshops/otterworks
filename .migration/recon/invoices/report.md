# Recon report: unit `invoices`

- **Verdict: PASS**
- Mode: `live`
- Mapping version: `m1`
- Tolerance version: `v1`
- Seed: `20260901` | Params: `{'batch_no': '85559852'}`
- Generated: 2026-09-01T04:43:18.706567+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 9 | PASS |
| 3 | keyed_diffs | 168713 | PASS |

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "invoices.invoice_no",
    "invoices.cust_id",
    "invoices.tenant_id",
    "invoices.status_cd",
    "invoices.total_amt",
    "invoices.batch_no",
    "invoices.legacy.invoice_dt",
    "invoices.legacy.due_dt"
  ]
}
```

## Tier 3 coverage
```json
{
  "invoices": {
    "mode": "full_diff",
    "population": 18750
  },
  "embeds_graded": {
    "invoices.lines": 149963
  }
}
```
