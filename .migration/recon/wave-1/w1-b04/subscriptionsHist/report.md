# Recon report: unit `subscriptionsHist`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-draft-4` (sha256 `f5f8df83ed10`)
- Tolerance version: `1` (sha256 `1a8ebb6c4c57`)
- Collections: `subscriptionsHist`
- Seed: `1`
- Generated: 2026-10-07T10:40:06.283362+00:00
- 8 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 3 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 1 | PASS |
| 3 | keyed_diffs | 0 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "subscriptionsHist": 0
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "subscriptionsHist.histDt",
    "subscriptionsHist.histOp",
    "subscriptionsHist.tenantId",
    "subscriptionsHist.planId",
    "subscriptionsHist.startsOn",
    "subscriptionsHist.endsOn",
    "subscriptionsHist.statusCd",
    "subscriptionsHist.suspendedOn"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "subscriptionsHist.histOp",
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
  "fields_fully_deferred": 7
}
```

## Tier 3 coverage
```json
{
  "subscriptionsHist": {
    "mode": "full_diff",
    "population": 0,
    "duplicate_source_key_count": 0
  }
}
```
