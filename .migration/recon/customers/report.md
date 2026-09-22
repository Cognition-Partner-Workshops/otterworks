# Recon report: unit `customers`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-22T21:08:08.517065+00:00
- **WARNING: embed customers.attributes: scoped by a where-predicate; extra target elements not checked**
- 317 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 205 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 4 | PASS |
| 2 | per_field_aggregates | 30 | PASS |
| 3 | keyed_diffs | 865 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "customers": 201,
    "customerVersions": 60,
    "entityAttrValue": 50
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "customers.custSeqNo",
    "customers.tenantId",
    "customers.custNo",
    "customers.custName",
    "customers.custNameUpper",
    "customers.legalName",
    "customers.dbaName",
    "customers.addrLine1",
    "customers.addrLine2",
    "customers.addrLine3",
    "customers.addrLine4",
    "customers.addrLine5",
    "customers.addrLine6",
    "customers.city",
    "customers.stateCd",
    "customers.zip",
    "customers.zip4",
    "customers.countryCd",
    "customers.mailAddrLine1",
    "customers.mailAddrLine2",
    "customers.mailAddrLine3",
    "customers.mailAddrLine4",
    "customers.mailAddrLine5",
    "customers.mailAddrLine6",
    "customers.mailCity",
    "customers.mailStateCd",
    "customers.mailZip",
    "customers.phone1",
    "customers.phone2",
    "customers.phone3",
    "customers.phone4",
    "customers.phone1TypeCd",
    "customers.phone2TypeCd",
    "customers.phone3TypeCd",
    "customers.phone4TypeCd",
    "customers.fax",
    "customers.email1",
    "customers.email2",
    "customers.email3",
    "customers.signupDt",
    "customers.lastActivityDt",
    "customers.lastInvoiceDt",
    "customers.lastPaymentDt",
    "customers.terminateDt",
    "customers.statusCd",
    "customers.subStatusCd",
    "customers.custTypeCd",
    "customers.segmentCd",
    "customers.regionCd",
    "customers.territoryCd",
    "customers.channelCd",
    "customers.rateClassCd",
    "customers.taxExempt",
    "customers.creditHold",
    "customers.dunningExempt",
    "customers.vip",
    "customers.curBalAmt",
    "customers.pastDueAmt",
    "customers.ytdBilledAmt",
    "customers.ltdBilledAmt",
    "customers.ytdPaidAmt",
    "customers.creditLimitAmt",
    "customers.relatedAcctIds",
    "customers.childAcctIds",
    "customers.promoCodes",
    "customers.contactNotes",
    "customers.legacySysKey",
    "customers.mainframeAcctNo",
    "customers.conversionBatchNo",
    "customers.flag01",
    "customers.flag02",
    "customers.flag03",
    "customers.flag04",
    "customers.flag05",
    "customers.flag06",
    "customers.flag07",
    "customers.flag08",
    "customers.flag09",
    "customers.flag10",
    "customers.flag11",
    "customers.flag12",
    "customers.flag13",
    "customers.flag14",
    "customers.flag15",
    "customers.flag16",
    "customers.flag17",
    "customers.flag18",
    "customers.flag19",
    "customers.flag20",
    "customers.udf01",
    "customers.udf02",
    "customers.udf03",
    "customers.udf04",
    "customers.udf05",
    "customers.udf06",
    "customers.udf07",
    "customers.udf08",
    "customers.udf09",
    "customers.udf10",
    "customers.udf11",
    "customers.udf12",
    "customers.udf13",
    "customers.udf14",
    "customers.udf15",
    "customers.udf16",
    "customers.udf17",
    "customers.udf18",
    "customers.udf19",
    "customers.udf20",
    "customers.udf21",
    "customers.udf22",
    "customers.udf23",
    "customers.udf24",
    "customers.udf25",
    "customers.udf26",
    "customers.udf27",
    "customers.udf28",
    "customers.udf29",
    "customers.udf30",
    "customers.udf31",
    "customers.udf32",
    "customers.udf33",
    "customers.udf34",
    "customers.udf35",
    "customers.udf36",
    "customers.udf37",
    "customers.udf38",
    "customers.udf39",
    "customers.udf40",
    "customers.udfAmt01",
    "customers.udfAmt02",
    "customers.udfAmt03",
    "customers.udfAmt04",
    "customers.udfAmt05",
    "customers.udfAmt06",
    "customers.udfAmt07",
    "customers.udfAmt08",
    "customers.udfAmt09",
    "customers.udfAmt10",
    "customers.udfDt01",
    "customers.udfDt02",
    "customers.udfDt03",
    "customers.udfDt04",
    "customers.udfDt05",
    "customers.udfDt06",
    "customers.udfDt07",
    "customers.udfDt08",
    "customers.udfDt09",
    "customers.udfDt10",
    "customers.createdBy",
    "customers.createdDt",
    "customers.updatedBy",
    "customers.updatedDt",
    "customers.rowVersionNo",
    "customerVersions.histDt",
    "customerVersions.histOp",
    "customerVersions.custId",
    "customerVersions.custSeqNo",
    "customerVersions.tenantId",
    "customerVersions.custNo",
    "customerVersions.custName",
    "customerVersions.custNameUpper",
    "customerVersions.legalName",
    "customerVersions.dbaName",
    "customerVersions.addrLine1",
    "customerVersions.addrLine2",
    "customerVersions.addrLine3",
    "customerVersions.addrLine4",
    "customerVersions.addrLine5",
    "customerVersions.addrLine6",
    "customerVersions.city",
    "customerVersions.stateCd",
    "customerVersions.zip",
    "customerVersions.zip4",
    "customerVersions.countryCd",
    "customerVersions.mailAddrLine1",
    "customerVersions.mailAddrLine2",
    "customerVersions.mailAddrLine3",
    "customerVersions.mailAddrLine4",
    "customerVersions.mailAddrLine5",
    "customerVersions.mailAddrLine6",
    "customerVersions.mailCity",
    "customerVersions.mailStateCd",
    "customerVersions.mailZip",
    "customerVersions.phone1",
    "customerVersions.phone2",
    "customerVersions.phone3",
    "customerVersions.phone4",
    "customerVersions.phone1TypeCd",
    "customerVersions.phone2TypeCd",
    "customerVersions.phone3TypeCd",
    "customerVersions.phone4TypeCd",
    "customerVersions.fax",
    "customerVersions.email1",
    "customerVersions.email2",
    "customerVersions.email3",
    "customerVersions.signupDt",
    "customerVersions.lastActivityDt",
    "customerVersions.lastInvoiceDt",
    "customerVersions.lastPaymentDt",
    "customerVersions.terminateDt",
    "customerVersions.statusCd",
    "customerVersions.subStatusCd",
    "customerVersions.custTypeCd",
    "customerVersions.segmentCd",
    "customerVersions.regionCd",
    "customerVersions.territoryCd",
    "customerVersions.channelCd",
    "customerVersions.rateClassCd",
    "customerVersions.taxExempt",
    "customerVersions.creditHold",
    "customerVersions.dunningExempt",
    "customerVersions.vip",
    "customerVersions.curBalAmt",
    "customerVersions.pastDueAmt",
    "customerVersions.ytdBilledAmt",
    "customerVersions.ltdBilledAmt",
    "customerVersions.ytdPaidAmt",
    "customerVersions.creditLimitAmt",
    "customerVersions.relatedAcctIds",
    "customerVersions.childAcctIds",
    "customerVersions.promoCodes",
    "customerVersions.contactNotes",
    "customerVersions.legacySysKey",
    "customerVersions.mainframeAcctNo",
    "customerVersions.conversionBatchNo",
    "customerVersions.flag01",
    "customerVersions.flag02",
    "customerVersions.flag03",
    "customerVersions.flag04",
    "customerVersions.flag05",
    "customerVersions.flag06",
    "customerVersions.flag07",
    "customerVersions.flag08",
    "customerVersions.flag09",
    "customerVersions.flag10",
    "customerVersions.flag11",
    "customerVersions.flag12",
    "customerVersions.flag13",
    "customerVersions.flag14",
    "customerVersions.flag15",
    "customerVersions.flag16",
    "customerVersions.flag17",
    "customerVersions.flag18",
    "customerVersions.flag19",
    "customerVersions.flag20",
    "customerVersions.udf01",
    "customerVersions.udf02",
    "customerVersions.udf03",
    "customerVersions.udf04",
    "customerVersions.udf05",
    "customerVersions.udf06",
    "customerVersions.udf07",
    "customerVersions.udf08",
    "customerVersions.udf09",
    "customerVersions.udf10",
    "customerVersions.udf11",
    "customerVersions.udf12",
    "customerVersions.udf13",
    "customerVersions.udf14",
    "customerVersions.udf15",
    "customerVersions.udf16",
    "customerVersions.udf17",
    "customerVersions.udf18",
    "customerVersions.udf19",
    "customerVersions.udf20",
    "customerVersions.udf21",
    "customerVersions.udf22",
    "customerVersions.udf23",
    "customerVersions.udf24",
    "customerVersions.udf25",
    "customerVersions.udf26",
    "customerVersions.udf27",
    "customerVersions.udf28",
    "customerVersions.udf29",
    "customerVersions.udf30",
    "customerVersions.udf31",
    "customerVersions.udf32",
    "customerVersions.udf33",
    "customerVersions.udf34",
    "customerVersions.udf35",
    "customerVersions.udf36",
    "customerVersions.udf37",
    "customerVersions.udf38",
    "customerVersions.udf39",
    "customerVersions.udf40",
    "customerVersions.udfAmt01",
    "customerVersions.udfAmt02",
    "customerVersions.udfAmt03",
    "customerVersions.udfAmt04",
    "customerVersions.udfAmt05",
    "customerVersions.udfAmt06",
    "customerVersions.udfAmt07",
    "customerVersions.udfAmt08",
    "customerVersions.udfAmt09",
    "customerVersions.udfAmt10",
    "customerVersions.udfDt01",
    "customerVersions.udfDt02",
    "customerVersions.udfDt03",
    "customerVersions.udfDt04",
    "customerVersions.udfDt05",
    "customerVersions.udfDt06",
    "customerVersions.udfDt07",
    "customerVersions.udfDt08",
    "customerVersions.udfDt09",
    "customerVersions.udfDt10",
    "customerVersions.createdBy",
    "customerVersions.createdDt",
    "customerVersions.updatedBy",
    "customerVersions.updatedDt",
    "customerVersions.rowVersionNo",
    "entityAttrValue.entityType",
    "entityAttrValue.entityId",
    "entityAttrValue.attrName",
    "entityAttrValue.attrValue",
    "entityAttrValue.attrType",
    "entityAttrValue.createdDt"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "customers.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.custNo",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.custName",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.custNameUpper",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.legalName",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.dbaName",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.addrLine1",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.addrLine2",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.addrLine3",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.addrLine4",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.addrLine5",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.addrLine6",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.city",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.stateCd",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.zip",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.zip4",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.countryCd",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.mailAddrLine1",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.mailAddrLine2",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.mailAddrLine3",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.mailAddrLine4",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.mailAddrLine5",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.mailAddrLine6",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.mailCity",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.mailStateCd",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.mailZip",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.phone1",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.phone2",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.phone3",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.phone4",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.fax",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.email1",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.email2",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.email3",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.contactNotes",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.legacySysKey",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.mainframeAcctNo",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag01",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag02",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag03",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag04",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag05",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag06",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag07",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag08",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag09",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag10",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag11",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag12",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag13",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag14",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag15",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag16",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag17",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag18",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag19",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.flag20",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf01",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf02",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf03",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf04",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf05",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf06",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf07",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf08",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf09",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf10",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf11",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf12",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf13",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf14",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf15",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf16",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf17",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf18",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf19",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf20",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf21",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf22",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf23",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf24",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf25",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf26",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf27",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf28",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf29",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf30",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf31",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf32",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf33",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf34",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf35",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf36",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf37",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf38",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf39",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.udf40",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.createdBy",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customers.updatedBy",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.histOp",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.custId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.custNo",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.custName",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.custNameUpper",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.legalName",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.dbaName",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.addrLine1",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.addrLine2",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.addrLine3",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.addrLine4",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.addrLine5",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.addrLine6",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.city",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.stateCd",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.zip",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.zip4",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.countryCd",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.mailAddrLine1",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.mailAddrLine2",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.mailAddrLine3",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.mailAddrLine4",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.mailAddrLine5",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.mailAddrLine6",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.mailCity",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.mailStateCd",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.mailZip",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.phone1",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.phone2",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.phone3",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.phone4",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.fax",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.email1",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.email2",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.email3",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.contactNotes",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.legacySysKey",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.mainframeAcctNo",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag01",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag02",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag03",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag04",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag05",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag06",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag07",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag08",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag09",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag10",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag11",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag12",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag13",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag14",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag15",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag16",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag17",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag18",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag19",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.flag20",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf01",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf02",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf03",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf04",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf05",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf06",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf07",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf08",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf09",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf10",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf11",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf12",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf13",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf14",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf15",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf16",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf17",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf18",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf19",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf20",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf21",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf22",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf23",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf24",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf25",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf26",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf27",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf28",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf29",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf30",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf31",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf32",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf33",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf34",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf35",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf36",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf37",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf38",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf39",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.udf40",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.createdBy",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerVersions.updatedBy",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "entityAttrValue.entityType",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "entityAttrValue.entityId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "entityAttrValue.attrName",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "entityAttrValue.attrValue",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "entityAttrValue.attrType",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 287
}
```

## Tier 3 coverage
```json
{
  "customers": {
    "mode": "full_diff",
    "population": 201,
    "duplicate_source_key_count": 0
  },
  "embed_extras_unchecked": [
    "customers.attributes"
  ],
  "embeds_graded": {
    "customers.attributes": 554
  },
  "customerVersions": {
    "mode": "full_diff",
    "population": 60,
    "duplicate_source_key_count": 0
  },
  "entityAttrValue": {
    "mode": "full_diff",
    "population": 50,
    "duplicate_source_key_count": 0
  }
}
```
