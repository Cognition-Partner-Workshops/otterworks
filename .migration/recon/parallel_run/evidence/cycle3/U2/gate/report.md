# Recon report: unit `U2`

- **Verdict: PASS**
- Mode: `live`
- Mapping version: `v1.0.1`
- Tolerance version: `v1`
- Seed: `714559852` | Params: `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-02T07:14:07.729136+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 9 | PASS |
| 3 | keyed_diffs | 168713 | PASS |

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "invoices.invoice_id",
    "invoices.invoice_no",
    "invoices.cust_id",
    "invoices.tenant_id",
    "invoices.invoice_dt",
    "invoices.due_dt"
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
