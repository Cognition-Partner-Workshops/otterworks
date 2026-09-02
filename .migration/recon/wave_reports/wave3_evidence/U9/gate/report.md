# Recon report: unit `U9`

- **Verdict: PASS**
- Mode: `live`
- Mapping version: `v1.0.1`
- Tolerance version: `v1`
- Seed: `714559852` | Params: `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-02T03:27:45.340796+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 7 | PASS |
| 2 | per_field_aggregates | 39 | PASS |
| 3 | keyed_diffs | 145 | PASS |
| 4 | app_level_parity | 5 | PASS |

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "replay_u9_tenants.id",
    "replay_u9_tenants.name",
    "replay_u9_tenants.tax_exempt_yn",
    "replay_u9_subscriptions.id",
    "replay_u9_subscriptions.tenant_id",
    "replay_u9_subscriptions.plan_id",
    "replay_u9_subscriptions_history.hist_dt",
    "replay_u9_subscriptions_history.hist_op",
    "replay_u9_subscriptions_history.id",
    "replay_u9_subscriptions_history.tenant_id",
    "replay_u9_subscriptions_history.plan_id",
    "replay_u9_billing_invoices.id",
    "replay_u9_billing_invoices.tenant_id",
    "replay_u9_billing_invoices.period_id",
    "replay_u9_dunning_attempts.id",
    "replay_u9_dunning_attempts.tenant_id",
    "replay_u9_dunning_attempts.invoice_id",
    "replay_u9_notifications.id",
    "replay_u9_notifications.tenant_id"
  ]
}
```

## Tier 3 coverage
```json
{
  "replay_u9_tenants": {
    "mode": "full_diff",
    "population": 69
  },
  "replay_u9_subscriptions": {
    "mode": "full_diff",
    "population": 69
  },
  "replay_u9_subscriptions_history": {
    "mode": "full_diff",
    "population": 0
  },
  "replay_u9_billing_invoices": {
    "mode": "full_diff",
    "population": 3
  },
  "embeds_graded": {
    "replay_u9_billing_invoices.lines": 2
  },
  "replay_u9_dunning_attempts": {
    "mode": "full_diff",
    "population": 1
  },
  "replay_u9_notifications": {
    "mode": "full_diff",
    "population": 1
  }
}
```
