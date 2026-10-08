# Recon report: unit `invoice-line`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-v1` (sha256 `a0e184e2ade2`)
- Tolerance version: `tol-1` (sha256 `a23d517a8e6d`)
- Collections: `invoiceLine`
- Seed: `0`
- Generated: 2026-10-08T12:51:13.618350+00:00
- 19 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 9 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 3 | PASS |
| 3 | keyed_diffs | 1500 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "invoiceLine": 1500
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "invoiceLine.invoiceNo",
    "invoiceLine.invoiceId",
    "invoiceLine.custId",
    "invoiceLine.custNo",
    "invoiceLine.custName",
    "invoiceLine.tenantId",
    "invoiceLine.lineNo",
    "invoiceLine.lineTypeCd",
    "invoiceLine.itemDesc",
    "invoiceLine.qty",
    "invoiceLine.unitPrice",
    "invoiceLine.amount",
    "invoiceLine.taxAmt",
    "invoiceLine.invoiceDt",
    "invoiceLine.servicePeriod",
    "invoiceLine.posted",
    "invoiceLine.glAcct",
    "invoiceLine.batchNo",
    "invoiceLine.srcSystem"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "invoiceLine.invoiceNo",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "invoiceLine.invoiceId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "invoiceLine.custId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "invoiceLine.custNo",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "invoiceLine.custName",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "invoiceLine.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "invoiceLine.itemDesc",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "invoiceLine.servicePeriod",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "invoiceLine.srcSystem",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 16
}
```

## Tier 3 coverage
```json
{
  "invoiceLine": {
    "mode": "full_diff",
    "population": 1500,
    "duplicate_source_key_count": 0
  }
}
```
