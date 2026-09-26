# Recon report: unit `u-02-customers`

- **Verdict: FAIL** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging) | Target: `local` (local target: NOT a merge verdict)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-2`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-26T17:31:32.054025+00:00
- **WARNING: embed customerMaster.attributes: scoped by a where-predicate; extra target elements not checked**
- 311 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 220 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 3 | PASS |
| 2 | per_field_aggregates | 30 | PASS |
| 3 | keyed_diffs | 33338 | FAIL (63 findings) |

## Tier 1 coverage
```json
{
  "source_counts": {
    "customerMaster": 25001,
    "customerMasterHist": 0
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "customerMaster.custSeqNo",
    "customerMaster.tenantId",
    "customerMaster.custNo",
    "customerMaster.custName",
    "customerMaster.custNameUpper",
    "customerMaster.legalName",
    "customerMaster.dbaName",
    "customerMaster.addrLine1",
    "customerMaster.addrLine2",
    "customerMaster.addrLine3",
    "customerMaster.addrLine4",
    "customerMaster.addrLine5",
    "customerMaster.addrLine6",
    "customerMaster.city",
    "customerMaster.stateCd",
    "customerMaster.zip",
    "customerMaster.zip4",
    "customerMaster.countryCd",
    "customerMaster.mailAddrLine1",
    "customerMaster.mailAddrLine2",
    "customerMaster.mailAddrLine3",
    "customerMaster.mailAddrLine4",
    "customerMaster.mailAddrLine5",
    "customerMaster.mailAddrLine6",
    "customerMaster.mailCity",
    "customerMaster.mailStateCd",
    "customerMaster.mailZip",
    "customerMaster.phone1",
    "customerMaster.phone2",
    "customerMaster.phone3",
    "customerMaster.phone4",
    "customerMaster.phone1TypeCd",
    "customerMaster.phone2TypeCd",
    "customerMaster.phone3TypeCd",
    "customerMaster.phone4TypeCd",
    "customerMaster.fax",
    "customerMaster.email1",
    "customerMaster.email2",
    "customerMaster.email3",
    "customerMaster.signupDt",
    "customerMaster.lastActivityDt",
    "customerMaster.lastInvoiceDt",
    "customerMaster.lastPaymentDt",
    "customerMaster.terminateDt",
    "customerMaster.statusCd",
    "customerMaster.subStatusCd",
    "customerMaster.custTypeCd",
    "customerMaster.segmentCd",
    "customerMaster.regionCd",
    "customerMaster.territoryCd",
    "customerMaster.channelCd",
    "customerMaster.rateClassCd",
    "customerMaster.taxExempt",
    "customerMaster.creditHold",
    "customerMaster.dunningExempt",
    "customerMaster.vip",
    "customerMaster.curBalAmt",
    "customerMaster.pastDueAmt",
    "customerMaster.ytdBilledAmt",
    "customerMaster.ltdBilledAmt",
    "customerMaster.ytdPaidAmt",
    "customerMaster.creditLimitAmt",
    "customerMaster.relatedAcctIds",
    "customerMaster.childAcctIds",
    "customerMaster.promoCodes",
    "customerMaster.contactNotes",
    "customerMaster.legacySysKey",
    "customerMaster.mainframeAcctNo",
    "customerMaster.conversionBatchNo",
    "customerMaster.flag01",
    "customerMaster.flag02",
    "customerMaster.flag03",
    "customerMaster.flag04",
    "customerMaster.flag05",
    "customerMaster.flag06",
    "customerMaster.flag07",
    "customerMaster.flag08",
    "customerMaster.flag09",
    "customerMaster.flag10",
    "customerMaster.flag11",
    "customerMaster.flag12",
    "customerMaster.flag13",
    "customerMaster.flag14",
    "customerMaster.flag15",
    "customerMaster.flag16",
    "customerMaster.flag17",
    "customerMaster.flag18",
    "customerMaster.flag19",
    "customerMaster.flag20",
    "customerMaster.udf01",
    "customerMaster.udf02",
    "customerMaster.udf03",
    "customerMaster.udf04",
    "customerMaster.udf05",
    "customerMaster.udf06",
    "customerMaster.udf07",
    "customerMaster.udf08",
    "customerMaster.udf09",
    "customerMaster.udf10",
    "customerMaster.udf11",
    "customerMaster.udf12",
    "customerMaster.udf13",
    "customerMaster.udf14",
    "customerMaster.udf15",
    "customerMaster.udf16",
    "customerMaster.udf17",
    "customerMaster.udf18",
    "customerMaster.udf19",
    "customerMaster.udf20",
    "customerMaster.udf21",
    "customerMaster.udf22",
    "customerMaster.udf23",
    "customerMaster.udf24",
    "customerMaster.udf25",
    "customerMaster.udf26",
    "customerMaster.udf27",
    "customerMaster.udf28",
    "customerMaster.udf29",
    "customerMaster.udf30",
    "customerMaster.udf31",
    "customerMaster.udf32",
    "customerMaster.udf33",
    "customerMaster.udf34",
    "customerMaster.udf35",
    "customerMaster.udf36",
    "customerMaster.udf37",
    "customerMaster.udf38",
    "customerMaster.udf39",
    "customerMaster.udf40",
    "customerMaster.udfAmt01",
    "customerMaster.udfAmt02",
    "customerMaster.udfAmt03",
    "customerMaster.udfAmt04",
    "customerMaster.udfAmt05",
    "customerMaster.udfAmt06",
    "customerMaster.udfAmt07",
    "customerMaster.udfAmt08",
    "customerMaster.udfAmt09",
    "customerMaster.udfAmt10",
    "customerMaster.udfDt01",
    "customerMaster.udfDt02",
    "customerMaster.udfDt03",
    "customerMaster.udfDt04",
    "customerMaster.udfDt05",
    "customerMaster.udfDt06",
    "customerMaster.udfDt07",
    "customerMaster.udfDt08",
    "customerMaster.udfDt09",
    "customerMaster.udfDt10",
    "customerMaster.createdBy",
    "customerMaster.createdDt",
    "customerMaster.updatedBy",
    "customerMaster.updatedDt",
    "customerMaster.rowVersionNo",
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
    "customerMasterHist.rowVersionNo"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "customerMaster.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.custNo",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.custName",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.custNameUpper",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.legalName",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.dbaName",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.addrLine1",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.addrLine2",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.addrLine3",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.addrLine4",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.addrLine5",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.addrLine6",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.city",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.stateCd",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.zip",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.zip4",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.countryCd",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.mailAddrLine1",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.mailAddrLine2",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.mailAddrLine3",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.mailAddrLine4",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.mailAddrLine5",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.mailAddrLine6",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.mailCity",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.mailStateCd",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.mailZip",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.phone1",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.phone2",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.phone3",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.phone4",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.fax",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.email1",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.email2",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.email3",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.contactNotes",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.legacySysKey",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.mainframeAcctNo",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag01",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag02",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag03",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag04",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag05",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag06",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag07",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag08",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag09",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag10",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag11",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag12",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag13",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag14",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag15",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag16",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag17",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag18",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag19",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.flag20",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf01",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf02",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf03",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf04",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf05",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf06",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf07",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf08",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf09",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf10",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf11",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf12",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf13",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf14",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf15",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf16",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf17",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf18",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf19",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf20",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf21",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf22",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf23",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf24",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf25",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf26",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf27",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf28",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf29",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf30",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf31",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf32",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf33",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf34",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf35",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf36",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf37",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf38",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf39",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udf40",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udfDt01",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udfDt02",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udfDt03",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udfDt04",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udfDt05",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udfDt06",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udfDt07",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udfDt08",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udfDt09",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.udfDt10",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.createdBy",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "customerMaster.updatedBy",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
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
    }
  ],
  "fields_fully_deferred": 281
}
```

## Tier 3 coverage
```json
{
  "customerMaster": {
    "mode": "full_diff",
    "population": 25001,
    "duplicate_source_key_count": 0
  },
  "embed_extras_unchecked": [
    "customerMaster.attributes"
  ],
  "embeds_graded": {
    "customerMaster.attributes": 8337
  },
  "customerMasterHist": {
    "mode": "full_diff",
    "population": 0,
    "duplicate_source_key_count": 0
  }
}
```

## Tier 3 findings (63)
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:d557c1a68d55 | source=str:dc4e267ca091 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:38f32a47f070 | source=str:90fecf3946e8 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:8a13998e6893 | source=str:7a064df7c74e target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:3520d8e318e8 | source=str:ee9886933675 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:44d669717b34 | source=str:dc4e267ca091 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:1ed04c98695d | source=str:7cd8821d8d3d target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:0e6b15bdcca9 | source=str:7cd8821d8d3d target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:e45cd81615ac | source=str:7cd8821d8d3d target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field RELATED_ACCT_IDS->relatedAcctIds key=tuple:0e55541bb6dc | source=str:cc316ecab2ec target=missing | rules=['csv_to_array', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:075bb65fdd3d | source=str:dc4e267ca091 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:aaeba2f0f894 | source=str:ee9886933675 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:91c037911ca3 | source=str:ee9886933675 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:4e14db9a0e35 | source=str:7a064df7c74e target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:b231b176069f | source=str:f9f018ac29e0 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:65f1b7e2e144 | source=str:7a064df7c74e target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:3f0b1528168b | source=str:7cd8821d8d3d target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:5f4cb4fbffbe | source=str:90fecf3946e8 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field RELATED_ACCT_IDS->relatedAcctIds key=tuple:627473c9c57e | source=str:5c651bbdbcdf target=missing | rules=['csv_to_array', 'null_missing_equiv']
- `customerMaster` field_diff: field RELATED_ACCT_IDS->relatedAcctIds key=tuple:3976d0c98700 | source=str:cc316ecab2ec target=missing | rules=['csv_to_array', 'null_missing_equiv']
- `customerMaster` field_diff: field RELATED_ACCT_IDS->relatedAcctIds key=tuple:7e1f1398fb17 | source=str:5c651bbdbcdf target=missing | rules=['csv_to_array', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:ea2bcbffde39 | source=str:7cd8821d8d3d target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:984f119695ac | source=str:f6ee158f3e4f target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field RELATED_ACCT_IDS->relatedAcctIds key=tuple:775399c26c56 | source=str:5c651bbdbcdf target=missing | rules=['csv_to_array', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:9e49ce4539da | source=str:ee9886933675 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:1d5ec181fd06 | source=str:dc4e267ca091 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:546f3a031a56 | source=str:ee9886933675 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:a82ff5e57ce2 | source=str:f9f018ac29e0 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:1afb86ed2988 | source=str:dc4e267ca091 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field RELATED_ACCT_IDS->relatedAcctIds key=tuple:64b85e43d621 | source=str:5c651bbdbcdf target=missing | rules=['csv_to_array', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:fdba07f1b3d7 | source=str:7a064df7c74e target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:882a0b1f30b8 | source=str:adbdd7a248ba target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:f7d0a4dffa71 | source=str:f9f018ac29e0 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:47c3f1e38f30 | source=str:7cd8821d8d3d target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:69ad5f56156e | source=str:f9f018ac29e0 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field RELATED_ACCT_IDS->relatedAcctIds key=tuple:46ea9c204dbb | source=str:5c651bbdbcdf target=missing | rules=['csv_to_array', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:1d760732a96a | source=str:f6ee158f3e4f target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:6172d8531081 | source=str:f6ee158f3e4f target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field RELATED_ACCT_IDS->relatedAcctIds key=tuple:62c33909732d | source=str:5c651bbdbcdf target=missing | rules=['csv_to_array', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:962eb1709d5a | source=str:7cd8821d8d3d target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:7a3a2f08d097 | source=str:f9f018ac29e0 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:0676b6a32f36 | source=str:ee9886933675 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:2015d44e1ef3 | source=str:adbdd7a248ba target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:4518ceb91fdb | source=str:f9f018ac29e0 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:c314151ecdd8 | source=str:f6ee158f3e4f target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:15d90fcee79f | source=str:dc4e267ca091 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:2c4b35e77bdd | source=str:f6ee158f3e4f target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:f69befd81483 | source=str:f9f018ac29e0 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field RELATED_ACCT_IDS->relatedAcctIds key=tuple:cc35dfda6e9f | source=str:cc316ecab2ec target=missing | rules=['csv_to_array', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:85d7a1cffdb7 | source=str:ee9886933675 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:c2f8b30bc911 | source=str:90fecf3946e8 target=missing | rules=['date_string_to_date:dby-b3d57e!unconverted', 'null_missing_equiv']
- ... 13 more in result.json
