# Recon report: unit `subscriptions`

- **Verdict: FAIL** (values redacted)
- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-v2` (sha256 `ccd1078bedc9`)
- Tolerance version: `tol-1` (sha256 `a23d517a8e6d`)
- Collections: `subscriptions`, `subscriptionsHist`
- Seed: `0`
- Generated: 2026-10-08T13:07:32.457182+00:00
- 14 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 6 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 5 | PASS |
| 2 | per_field_aggregates | 3 | PASS |
| 3 | keyed_diffs | 46 | FAIL (6 findings) |

## Tier 1 coverage
```json
{
  "source_counts": {
    "subscriptions": 20,
    "subscriptionsHist": 6
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "subscriptions.tenantId",
    "subscriptions.planId",
    "subscriptions.startsOn",
    "subscriptions.endsOn",
    "subscriptions.suspendedOn",
    "subscriptionsHist.histDt",
    "subscriptionsHist.histOp",
    "subscriptionsHist.id",
    "subscriptionsHist.tenantId",
    "subscriptionsHist.planId",
    "subscriptionsHist.startsOn",
    "subscriptionsHist.endsOn",
    "subscriptionsHist.statusCd",
    "subscriptionsHist.suspendedOn"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "subscriptions.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "subscriptions.planId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "subscriptionsHist.histOp",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "subscriptionsHist.id",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "subscriptionsHist.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "subscriptionsHist.planId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 12
}
```

## Tier 3 coverage
```json
{
  "subscriptions": {
    "mode": "full_diff",
    "population": 20,
    "duplicate_source_key_count": 0
  },
  "subscriptionsHist": {
    "mode": "full_diff",
    "population": 6,
    "duplicate_source_key_count": 0
  }
}
```

## Tier 3 findings (6)
- `subscriptionsHist` field_diff: field HIST_DT->histDt key=tuple:28cb03b06c28 | source=str:d6c462864d56 target=str:d6c462864d56 | rules=['date_string_to_date!unconverted']
- `subscriptionsHist` field_diff: field HIST_DT->histDt key=tuple:0555debc8a65 | source=str:d6c462864d56 target=str:d6c462864d56 | rules=['date_string_to_date!unconverted']
- `subscriptionsHist` field_diff: field HIST_DT->histDt key=tuple:4079e4af87d7 | source=str:d6c462864d56 target=str:d6c462864d56 | rules=['date_string_to_date!unconverted']
- `subscriptionsHist` field_diff: field HIST_DT->histDt key=tuple:3912a1d67a34 | source=str:d6c462864d56 target=str:d6c462864d56 | rules=['date_string_to_date!unconverted']
- `subscriptionsHist` field_diff: field HIST_DT->histDt key=tuple:666aa17826ad | source=str:d6c462864d56 target=str:d6c462864d56 | rules=['date_string_to_date!unconverted']
- `subscriptionsHist` field_diff: field HIST_DT->histDt key=tuple:3af5d6e7f947 | source=str:d6c462864d56 target=str:d6c462864d56 | rules=['date_string_to_date!unconverted']
