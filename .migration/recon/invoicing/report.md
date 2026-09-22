# Recon report: unit `invoicing`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-22T21:27:56.090265+00:00
- 10 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 3 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 3 | PASS |
| 2 | per_field_aggregates | 8 | PASS |
| 3 | keyed_diffs | 183 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "invoices": 44,
    "creditNotes": 20
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
    "invoices.total",
    "creditNotes.tenantId",
    "creditNotes.issuedOn",
    "creditNotes.amount",
    "creditNotes.remainingAmount"
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
    },
    {
      "field": "creditNotes.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 3
}
```

## Tier 3 coverage
```json
{
  "invoices": {
    "mode": "full_diff",
    "population": 44,
    "duplicate_source_key_count": 0
  },
  "embeds_graded": {
    "invoices.lines": 119
  },
  "creditNotes": {
    "mode": "full_diff",
    "population": 20,
    "duplicate_source_key_count": 0
  }
}
```
