# Recon report: unit `u-10-plsql-invoicing`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging) | Target: `local` (local target: NOT a merge verdict)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3.1`
- Tolerance version: `tol-2`
- Seed: `1`
- Generated: 2026-09-26T18:48:47.125626+00:00
- 17 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 6 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 5 | PASS |
| 2 | per_field_aggregates | 16 | PASS |
| 3 | keyed_diffs | 19 | PASS |
| 4 | app_level_parity | 3 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "ratingPeriods": 3,
    "ratingResults": 3,
    "invoices": 4,
    "creditNotes": 5
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "ratingPeriods.tenantId",
    "ratingPeriods.periodStart",
    "ratingPeriods.periodEnd",
    "ratingResults.periodId",
    "ratingResults.subscriptionId",
    "ratingResults.overageAmount",
    "ratingResults.createdAt",
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
      "field": "ratingPeriods.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "ratingResults.periodId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "ratingResults.subscriptionId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
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
  "fields_fully_deferred": 6
}
```

## Tier 3 coverage
```json
{
  "ratingPeriods": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  },
  "ratingResults": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  },
  "invoices": {
    "mode": "full_diff",
    "population": 4,
    "duplicate_source_key_count": 0
  },
  "embeds_graded": {
    "invoices.lines": 4
  },
  "creditNotes": {
    "mode": "full_diff",
    "population": 5,
    "duplicate_source_key_count": 0
  }
}
```
