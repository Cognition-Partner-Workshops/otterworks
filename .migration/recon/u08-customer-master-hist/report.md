# Recon report: unit `u08-customer-master-hist`

- **Verdict: UNVERIFIED** (values redacted)
- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-v1.1` (sha256 `3dc4060d3a4b`)
- Tolerance version: `tol-1` (sha256 `a23d517a8e6d`)
- Collections: `customerMasterHist`
- Seed: `0`
- Generated: 2026-10-07T19:40:54.321381+00:00
- **WARNING: UNVERIFIED collection customerMasterHist: 0 source rows, key/shape/field rules unexercised**
- 163 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 117 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 21 | PASS |
| 3 | keyed_diffs | 0 | PASS |
| 4 | app_level_parity | 2 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "customerMasterHist": 0
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "customerMasterHist.histDt",
    "customerMasterHist.histOp",
    "customerMasterHist.custId",
    "customerMasterHist.custSeqNo",
    "customerMasterHist.tenantId",
    "customerMasterHist.custNo",
    "customerMasterHist.custName",
    "customerMasterHist.custNameUpper",
    "customerMasterHist.legalName",
    "customerMasterHist.dbaName",
    "customerMasterHist.addrLine1",
    "customerMasterHist.addrLine2",
    "customerMasterHist.addrLine3",
    "customerMasterHist.addrLine4",
    "customerMasterHist.addrLine5",
    "customerMasterHist.addrLine6",
    "customerMasterHist.city",
    "customerMasterHist.stateCd",
    "customerMasterHist.zip",
    "customerMasterHist.zip4",
    "customerMasterHist.countryCd",
    "customerMasterHist.mailAddrLine1",
    "customerMasterHist.mailAddrLine2",
    "customerMasterHist.mailAddrLine3",
    "customerMasterHist.mailAddrLine4",
    "customerMasterHist.mailAddrLine5",
    "customerMasterHist.mailAddrLine6",
    "customerMasterHist.mailCity",
    "customerMasterHist.mailStateCd",
    "customerMasterHist.mailZip",
    "customerMasterHist.phone1",
    "customerMasterHist.phone2",
    "customerMasterHist.phone3",
    "customerMasterHist.phone4",
    "customerMasterHist.phone1TypeCd",
    "customerMasterHist.phone2TypeCd",
    "customerMasterHist.phone3TypeCd",
    "customerMasterHist.phone4TypeCd",
    "customerMasterHist.fax",
    "customerMasterHist.email1",
    "customerMasterHist.email2",
    "customerMasterHist.email3",
    "customerMasterHist.signupDt",
    "customerMasterHist.lastActivityDt",
    "customerMasterHist.lastInvoiceDt",
    "customerMasterHist.lastPaymentDt",
    "customerMasterHist.terminateDt",
    "customerMasterHist.statusCd",
    "customerMasterHist.subStatusCd",
    "customerMasterHist.custTypeCd",
    "customerMasterHist.segmentCd",
    "customerMasterHist.regionCd",
    "customerMasterHist.territoryCd",
    "customerMasterHist.channelCd",
    "customerMasterHist.rateClassCd",
    "customerMasterHist.taxExempt",
    "customerMasterHist.creditHold",
    "customerMasterHist.dunningExempt",
    "customerMasterHist.vip",
    "customerMasterHist.curBalAmt",
    "customerMasterHist.pastDueAmt",
    "customerMasterHist.ytdBilledAmt",
    "customerMasterHist.ltdBilledAmt",
    "customerMasterHist.ytdPaidAmt",
    "customerMasterHist.creditLimitAmt",
    "customerMasterHist.relatedAcctIds",
    "customerMasterHist.childAcctIds",
    "customerMasterHist.promoCodes",
    "customerMasterHist.contactNotes",
    "customerMasterHist.legacySysKey",
    "customerMasterHist.mainframeAcctNo",
    "customerMasterHist.conversionBatchNo",
    "customerMasterHist.flag01",
    "customerMasterHist.flag02",
    "customerMasterHist.flag03",
    "customerMasterHist.flag04",
    "customerMasterHist.flag05",
    "customerMasterHist.flag06",
    "customerMasterHist.flag07",
    "customerMasterHist.flag08",
    "customerMasterHist.flag09",
    "customerMasterHist.flag10",
    "customerMasterHist.flag11",
    "customerMasterHist.flag12",
    "customerMasterHist.flag13",
    "customerMasterHist.flag14",
    "customerMasterHist.flag15",
    "customerMasterHist.flag16",
    "customerMasterHist.flag17",
    "customerMasterHist.flag18",
    "customerMasterHist.flag19",
    "customerMasterHist.flag20",
    "customerMasterHist.udf01",
    "customerMasterHist.udf02",
    "customerMasterHist.udf03",
    "customerMasterHist.udf04",
    "customerMasterHist.udf05",
    "customerMasterHist.udf06",
    "customerMasterHist.udf07",
    "customerMasterHist.udf08",
    "customerMasterHist.udf09",
    "customerMasterHist.udf10",
    "customerMasterHist.udf11",
    "customerMasterHist.udf12",
    "customerMasterHist.udf13",
    "customerMasterHist.udf14",
    "customerMasterHist.udf15",
    "customerMasterHist.udf16",
    "customerMasterHist.udf17",
    "customerMasterHist.udf18",
    "customerMasterHist.udf19",
    "customerMasterHist.udf20",
    "customerMasterHist.udf21",
    "customerMasterHist.udf22",
    "customerMasterHist.udf23",
    "customerMasterHist.udf24",
    "customerMasterHist.udf25",
    "customerMasterHist.udf26",
    "customerMasterHist.udf27",
    "customerMasterHist.udf28",
    "customerMasterHist.udf29",
    "customerMasterHist.udf30",
    "customerMasterHist.udf31",
    "customerMasterHist.udf32",
    "customerMasterHist.udf33",
    "customerMasterHist.udf34",
    "customerMasterHist.udf35",
    "customerMasterHist.udf36",
    "customerMasterHist.udf37",
    "customerMasterHist.udf38",
    "customerMasterHist.udf39",
    "customerMasterHist.udf40",
    "customerMasterHist.udfAmt01",
    "customerMasterHist.udfAmt02",
    "customerMasterHist.udfAmt03",
    "customerMasterHist.udfAmt04",
    "customerMasterHist.udfAmt05",
    "customerMasterHist.udfAmt06",
    "customerMasterHist.udfAmt07",
    "customerMasterHist.udfAmt08",
    "customerMasterHist.udfAmt09",
    "customerMasterHist.udfAmt10",
    "customerMasterHist.udfDt01",
    "customerMasterHist.udfDt02",
    "customerMasterHist.udfDt03",
    "customerMasterHist.udfDt04",
    "customerMasterHist.udfDt05",
    "customerMasterHist.udfDt06",
    "customerMasterHist.udfDt07",
    "customerMasterHist.udfDt08",
    "customerMasterHist.udfDt09",
    "customerMasterHist.udfDt10",
    "customerMasterHist.createdBy",
    "customerMasterHist.createdDt",
    "customerMasterHist.updatedBy",
    "customerMasterHist.updatedDt",
    "customerMasterHist.rowVersionNo",
    "customerMasterHist.histDtRaw",
    "customerMasterHist.signupDtRaw",
    "customerMasterHist.lastActivityDtRaw",
    "customerMasterHist.lastInvoiceDtRaw",
    "customerMasterHist.lastPaymentDtRaw",
    "customerMasterHist.terminateDtRaw"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "customerMasterHist.histOp",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.custId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.custNo",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.custName",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.custNameUpper",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.legalName",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.dbaName",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.addrLine1",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.addrLine2",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.addrLine3",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.addrLine4",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.addrLine5",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.addrLine6",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.city",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.stateCd",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.zip",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.zip4",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.countryCd",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.mailAddrLine1",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.mailAddrLine2",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.mailAddrLine3",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.mailAddrLine4",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.mailAddrLine5",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.mailAddrLine6",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.mailCity",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.mailStateCd",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.mailZip",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.phone1",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.phone2",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.phone3",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.phone4",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.fax",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.email1",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.email2",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.email3",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.contactNotes",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.legacySysKey",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.mainframeAcctNo",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag01",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag02",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag03",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag04",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag05",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag06",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag07",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag08",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag09",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag10",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag11",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag12",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag13",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag14",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag15",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag16",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag17",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag18",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag19",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.flag20",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf01",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf02",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf03",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf04",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf05",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf06",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf07",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf08",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf09",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf10",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf11",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf12",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf13",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf14",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf15",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf16",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf17",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf18",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf19",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf20",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf21",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf22",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf23",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf24",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf25",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf26",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf27",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf28",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf29",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf30",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf31",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf32",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf33",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf34",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf35",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf36",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf37",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf38",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf39",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udf40",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udfDt01",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udfDt02",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udfDt03",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udfDt04",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udfDt05",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udfDt06",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udfDt07",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udfDt08",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udfDt09",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.udfDt10",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.createdBy",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.updatedBy",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.histDtRaw",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.signupDtRaw",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.lastActivityDtRaw",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.lastInvoiceDtRaw",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.lastPaymentDtRaw",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMasterHist.terminateDtRaw",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 142
}
```

## Tier 3 coverage
```json
{
  "customerMasterHist": {
    "mode": "full_diff",
    "population": 0,
    "duplicate_source_key_count": 0
  }
}
```
