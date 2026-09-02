# Recon report: unit `U6`

- **Verdict: PASS**
- Mode: `live`
- Mapping version: `v1.0.1`
- Tolerance version: `v1`
- Seed: `714559852` | Params: `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-02T05:42:49.736567+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 14 | PASS |
| 2 | per_field_aggregates | 67 | PASS |
| 3 | keyed_diffs | 1006 | PASS |
| 4 | app_level_parity | 5 | PASS |

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "replay_u6_codes.code_type",
    "replay_u6_codes.code_desc",
    "replay_u6_tenants.id",
    "replay_u6_tenants.name",
    "replay_u6_tenants.tax_exempt_yn",
    "replay_u6_plans.id",
    "replay_u6_plans.code",
    "replay_u6_plans.active_yn",
    "replay_u6_subscriptions.id",
    "replay_u6_subscriptions.tenant_id",
    "replay_u6_subscriptions.plan_id",
    "replay_u6_subscriptions_history.hist_dt",
    "replay_u6_subscriptions_history.hist_op",
    "replay_u6_subscriptions_history.id",
    "replay_u6_subscriptions_history.tenant_id",
    "replay_u6_subscriptions_history.plan_id",
    "replay_u6_usage_events.id",
    "replay_u6_usage_events.tenant_id",
    "replay_u6_rating_periods.id",
    "replay_u6_rating_periods.tenant_id",
    "replay_u6_billing_invoices.id",
    "replay_u6_billing_invoices.tenant_id",
    "replay_u6_billing_invoices.period_id",
    "replay_u6_credit_notes.id",
    "replay_u6_credit_notes.tenant_id",
    "replay_u6_dunning_attempts.id",
    "replay_u6_dunning_attempts.tenant_id",
    "replay_u6_dunning_attempts.invoice_id",
    "replay_u6_notifications.id",
    "replay_u6_notifications.tenant_id",
    "replay_u6_billing_audit_log.module",
    "replay_u6_billing_audit_log.message"
  ]
}
```

## Tier 3 coverage
```json
{
  "replay_u6_codes": {
    "mode": "full_diff",
    "population": 32
  },
  "replay_u6_tenants": {
    "mode": "full_diff",
    "population": 69
  },
  "replay_u6_plans": {
    "mode": "full_diff",
    "population": 3
  },
  "replay_u6_subscriptions": {
    "mode": "full_diff",
    "population": 69
  },
  "replay_u6_subscriptions_history": {
    "mode": "full_diff",
    "population": 0
  },
  "replay_u6_usage_events": {
    "mode": "full_diff",
    "population": 814
  },
  "replay_u6_rating_periods": {
    "mode": "full_diff",
    "population": 3
  },
  "embeds_graded": {
    "replay_u6_rating_periods.results": 3,
    "replay_u6_billing_invoices.lines": 2
  },
  "replay_u6_billing_invoices": {
    "mode": "full_diff",
    "population": 3
  },
  "replay_u6_credit_notes": {
    "mode": "full_diff",
    "population": 5
  },
  "replay_u6_dunning_attempts": {
    "mode": "full_diff",
    "population": 1
  },
  "replay_u6_notifications": {
    "mode": "full_diff",
    "population": 1
  },
  "replay_u6_billing_audit_log": {
    "mode": "full_diff",
    "population": 1
  }
}
```
