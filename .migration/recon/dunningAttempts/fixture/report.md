# Recon report: unit `dunningAttempts`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-4` (sha256 `f5f8df83ed10`)
- Tolerance version: `1` (sha256 `1a8ebb6c4c57`)
- Collections: `dunningAttempts`
- Seed: `1`
- Generated: 2026-10-07T10:26:18.353409+00:00
- 3 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 2 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 3 | PASS |
| 3 | keyed_diffs | 1 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "dunningAttempts": 1
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
    "population": 1,
    "duplicate_source_key_count": 0
  }
}
```
