# Recon report: unit `dunning-attempts`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-v3` (sha256 `c158f8bb469d`)
- Tolerance version: `tol-1` (sha256 `a23d517a8e6d`)
- Collections: `dunningAttempts`
- Seed: `0`
- Generated: 2026-10-08T13:34:41.173306+00:00
- 3 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 2 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 3 | PASS |
| 3 | keyed_diffs | 3 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "dunningAttempts": 3
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "dunningAttempts.tenantId",
    "dunningAttempts.invoiceId",
    "dunningAttempts.scheduledFor"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "dunningAttempts.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "dunningAttempts.invoiceId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 2
}
```

## Tier 3 coverage
```json
{
  "dunningAttempts": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  }
}
```
