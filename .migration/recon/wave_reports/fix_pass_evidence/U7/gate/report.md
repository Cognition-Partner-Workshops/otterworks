# Recon report: unit `U7`

- **Verdict: PASS**
- Mode: `live`
- Mapping version: `v1.0.1`
- Tolerance version: `v1`
- Seed: `714559852` | Params: `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-02T06:49:54.103595+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 5 | PASS |
| 2 | per_field_aggregates | 23 | PASS |
| 3 | keyed_diffs | 892 | PASS |
| 4 | app_level_parity | 8 | PASS |

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "replay_u7_plans.id",
    "replay_u7_plans.code",
    "replay_u7_plans.active_yn",
    "replay_u7_subscriptions.id",
    "replay_u7_subscriptions.tenant_id",
    "replay_u7_subscriptions.plan_id",
    "replay_u7_usage_events.id",
    "replay_u7_usage_events.tenant_id",
    "replay_u7_rating_periods.id",
    "replay_u7_rating_periods.tenant_id"
  ]
}
```

## Tier 3 coverage
```json
{
  "replay_u7_plans": {
    "mode": "full_diff",
    "population": 3
  },
  "replay_u7_subscriptions": {
    "mode": "full_diff",
    "population": 69
  },
  "replay_u7_usage_events": {
    "mode": "full_diff",
    "population": 814
  },
  "replay_u7_rating_periods": {
    "mode": "full_diff",
    "population": 3
  },
  "embeds_graded": {
    "replay_u7_rating_periods.results": 3
  }
}
```
