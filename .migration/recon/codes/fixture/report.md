# Recon report: unit `codes`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-2` (sha256 `232efbd7d88b`)
- Tolerance version: `1` (sha256 `1a8ebb6c4c57`)
- Collections: `codes`
- Seed: `1`
- Generated: 2026-10-07T08:52:43.452919+00:00
- 1 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 1 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 0 | PASS |
| 3 | keyed_diffs | 32 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "codes": 32
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "codes.codeDesc"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "codes.codeDesc",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 1
}
```

## Tier 3 coverage
```json
{
  "codes": {
    "mode": "full_diff",
    "population": 32,
    "duplicate_source_key_count": 0
  }
}
```
