# Recon report: unit `u04-invoices`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-v1.1` (sha256 `3dc4060d3a4b`)
- Tolerance version: `tol-1` (sha256 `a23d517a8e6d`)
- Collections: `invoices`
- Seed: `0`
- Generated: 2026-10-07T20:06:21.289704+00:00
- 6 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 2 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 9 | PASS |
| 2 | per_field_aggregates | 5 | PASS |
| 3 | keyed_diffs | 43 | PASS |
| 4 | app_level_parity | 3 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "invoices": 9
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "invoices.tenantId",
    "invoices.periodId",
    "invoices.issuedAt",
    "invoices.subtotal",
    "invoices.tax",
    "invoices.total"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "invoices.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "invoices.periodId",
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
  "invoices": {
    "mode": "full_diff",
    "population": 9,
    "duplicate_source_key_count": 0
  },
  "embeds_graded": {
    "invoices.lines": 29,
    "invoices.dunningAttempts": 5
  }
}
```
