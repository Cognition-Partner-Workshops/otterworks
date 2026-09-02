# Recon report: unit `U7`

- **Verdict: PASS**
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `v1.0.1`
- Tolerance version: `v1`
- Seed: `714559852`
- Generated: 2026-09-02T06:22:37.880004+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 5 | PASS |
| 2 | per_field_aggregates | 23 | PASS |
| 3 | keyed_diffs | 892 | PASS |
| 4 | app_level_parity | 8 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "PLANS": 3,
    "SUBSCRIPTIONS": 69,
    "USAGE_EVENTS": 814,
    "RATING_PERIODS": 3
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "replay_u7_plans.id",
    "replay_u7_plans.code",
    "replay_u7_plans.monthly_fee",
    "replay_u7_plans.overage_rate",
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
    "population": 3,
    "duplicate_source_key_count": 0
  },
  "replay_u7_subscriptions": {
    "mode": "full_diff",
    "population": 69,
    "duplicate_source_key_count": 0
  },
  "replay_u7_usage_events": {
    "mode": "full_diff",
    "population": 814,
    "duplicate_source_key_count": 0
  },
  "replay_u7_rating_periods": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  },
  "embeds_graded": {
    "replay_u7_rating_periods.results": 3
  }
}
```
