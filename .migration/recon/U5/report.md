# Recon report: unit `U5`

- **Verdict: PASS**
- Mode: `live`
- Mapping version: `v1.0.1`
- Tolerance version: `v1`
- Seed: `714559852` | Params: `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-02T00:26:37.566626+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 11 | PASS |
| 2 | per_field_aggregates | 53 | PASS |
| 3 | keyed_diffs | 901 | PASS |

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "subscriptions.id",
    "subscriptions.tenant_id",
    "subscriptions.plan_id",
    "subscriptions_history.hist_dt",
    "subscriptions_history.hist_op",
    "subscriptions_history.id",
    "subscriptions_history.tenant_id",
    "subscriptions_history.plan_id",
    "usage_events.id",
    "usage_events.tenant_id",
    "rating_periods.id",
    "rating_periods.tenant_id",
    "billing_invoices.id",
    "billing_invoices.tenant_id",
    "billing_invoices.period_id",
    "credit_notes.id",
    "credit_notes.tenant_id",
    "dunning_attempts.id",
    "dunning_attempts.tenant_id",
    "dunning_attempts.invoice_id",
    "notifications.id",
    "notifications.tenant_id",
    "billing_audit_log.module",
    "billing_audit_log.message"
  ]
}
```

## Tier 3 coverage
```json
{
  "subscriptions": {
    "mode": "full_diff",
    "population": 69
  },
  "subscriptions_history": {
    "mode": "full_diff",
    "population": 0
  },
  "usage_events": {
    "mode": "full_diff",
    "population": 814
  },
  "rating_periods": {
    "mode": "full_diff",
    "population": 3
  },
  "embeds_graded": {
    "rating_periods.results": 3,
    "billing_invoices.lines": 2
  },
  "billing_invoices": {
    "mode": "full_diff",
    "population": 3
  },
  "credit_notes": {
    "mode": "full_diff",
    "population": 5
  },
  "dunning_attempts": {
    "mode": "full_diff",
    "population": 1
  },
  "notifications": {
    "mode": "full_diff",
    "population": 1
  },
  "billing_audit_log": {
    "mode": "full_diff",
    "population": 0
  }
}
```
