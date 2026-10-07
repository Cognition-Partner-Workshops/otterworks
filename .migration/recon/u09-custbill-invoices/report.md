# Recon report: unit `u09-custbill-invoices`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-v1.1` (sha256 `3dc4060d3a4b`)
- Tolerance version: `tol-1` (sha256 `a23d517a8e6d`)
- Collections: `invoiceHeader`, `invoiceLine`
- Seed: `0`
- Generated: 2026-10-07T19:41:11.838184+00:00
- 30 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 15 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 8 | PASS |
| 3 | keyed_diffs | 2500 | PASS |
| 4 | app_level_parity | 3 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "invoiceHeader": 1000,
    "invoiceLine": 1500
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "invoiceHeader.invoiceNo",
    "invoiceHeader.custId",
    "invoiceHeader.tenantId",
    "invoiceHeader.invoiceDt",
    "invoiceHeader.dueDt",
    "invoiceHeader.statusCd",
    "invoiceHeader.totalAmt",
    "invoiceHeader.batchNo",
    "invoiceHeader.invoiceDtRaw",
    "invoiceHeader.dueDtRaw",
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
    "invoiceLine.srcSystem",
    "invoiceLine.invoiceDtRaw"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "invoiceHeader.invoiceNo",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "invoiceHeader.custId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "invoiceHeader.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "invoiceHeader.invoiceDtRaw",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "invoiceHeader.dueDtRaw",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
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
    },
    {
      "field": "invoiceLine.invoiceDtRaw",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 22
}
```

## Tier 3 coverage
```json
{
  "invoiceHeader": {
    "mode": "full_diff",
    "population": 1000,
    "duplicate_source_key_count": 0
  },
  "invoiceLine": {
    "mode": "full_diff",
    "population": 1500,
    "duplicate_source_key_count": 0
  }
}
```
