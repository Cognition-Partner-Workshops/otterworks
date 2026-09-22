# Recon report: unit `codes`

- **Verdict: FAIL** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-22T20:47:31.303656+00:00
- 1 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 1 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 0 | PASS |
| 3 | keyed_diffs | 42 | FAIL (2 findings) |

## Tier 1 coverage
```json
{
  "source_counts": {
    "codes": 41
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
    "population": 41,
    "duplicate_source_key_count": 0
  }
}
```

## Tier 3 findings (2)
- `codes` missing_doc: missing document key=tuple:2f06660fde32
- `codes` extra_doc: extra document key=tuple:73f0fad491ac
