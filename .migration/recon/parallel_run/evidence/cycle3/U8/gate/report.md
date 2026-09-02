# Recon report: unit `U8`

- **Verdict: PASS**
- Mode: `live`
- Mapping version: `v1.0.1`
- Tolerance version: `v1`
- Seed: `714559852` | Params: `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-02T05:43:17.113266+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 8 | PASS |
| 2 | per_field_aggregates | 36 | PASS |
| 3 | keyed_diffs | 902 | PASS |
| 4 | app_level_parity | 6 | PASS |

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "replay_u8_plans.id",
    "replay_u8_plans.code",
    "replay_u8_plans.active_yn",
    "replay_u8_subscriptions.id",
    "replay_u8_subscriptions.tenant_id",
    "replay_u8_subscriptions.plan_id",
    "replay_u8_usage_events.id",
    "replay_u8_usage_events.tenant_id",
    "replay_u8_rating_periods.id",
    "replay_u8_rating_periods.tenant_id",
    "replay_u8_billing_invoices.id",
    "replay_u8_billing_invoices.tenant_id",
    "replay_u8_billing_invoices.period_id",
    "replay_u8_credit_notes.id",
    "replay_u8_credit_notes.tenant_id"
  ]
}
```

## Tier 3 coverage
```json
{
  "replay_u8_plans": {
    "mode": "full_diff",
    "population": 3
  },
  "replay_u8_subscriptions": {
    "mode": "full_diff",
    "population": 69
  },
  "replay_u8_usage_events": {
    "mode": "full_diff",
    "population": 814
  },
  "replay_u8_rating_periods": {
    "mode": "full_diff",
    "population": 3
  },
  "embeds_graded": {
    "replay_u8_rating_periods.results": 3,
    "replay_u8_billing_invoices.lines": 2
  },
  "replay_u8_billing_invoices": {
    "mode": "full_diff",
    "population": 3
  },
  "replay_u8_credit_notes": {
    "mode": "full_diff",
    "population": 5
  }
}
```
