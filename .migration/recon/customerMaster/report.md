# Recon report: unit `customerMaster`

- **Verdict: FAIL** (values redacted)
- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-2` (sha256 `232efbd7d88b`)
- Tolerance version: `1` (sha256 `1a8ebb6c4c57`)
- Collections: `customerMaster`
- Seed: `1`
- Generated: 2026-10-07T08:55:00.104047+00:00
- 154 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 109 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 3 | PASS |
| 2 | per_field_aggregates | 15 | PASS |
| 3 | keyed_diffs | 271 | FAIL (44 findings) |

## Tier 1 coverage
```json
{
  "source_counts": {
    "customerMaster": 201
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
    "customerMaster.rowVersionNo"
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
    }
  ],
  "fields_fully_deferred": 139
}
```

## Tier 3 coverage
```json
{
  "customerMaster": {
    "mode": "full_diff",
    "population": 201,
    "duplicate_source_key_count": 0
  },
  "embeds_graded": {
    "customerMaster.attributes": 70
  }
}
```

## Tier 3 findings (44)
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:5612bc348b8f | source=str:7a064df7c74e target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:fc0a77a9f9da | source=str:f9f018ac29e0 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:bb6e05db9415 | source=str:ee9886933675 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:ce269a7125e3 | source=str:7a064df7c74e target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:ec75aafa8388 | source=str:dc4e267ca091 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:ab1f2458d24c | source=str:adbdd7a248ba target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:9e13379d4507 | source=str:dc4e267ca091 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:4e5b23fdb60c | source=str:f6ee158f3e4f target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:65e0b7f32f51 | source=str:adbdd7a248ba target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:ea83bf4fabf7 | source=str:f9f018ac29e0 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:960949a07b47 | source=str:f6ee158f3e4f target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:095433de06c7 | source=str:dc4e267ca091 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:1ef260ec4bb1 | source=str:90fecf3946e8 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:3db9a3b1714c | source=str:ee9886933675 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:2c2a98ab18dd | source=str:90fecf3946e8 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:db509400dbe6 | source=str:ee9886933675 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:e397c4df7f67 | source=str:adbdd7a248ba target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:07201ef90684 | source=str:f9f018ac29e0 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:89fc811bc282 | source=str:f9f018ac29e0 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:5bfa946df91a | source=str:dc4e267ca091 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:fc1a07169a62 | source=str:ee9886933675 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:c9296e9efeb4 | source=str:90fecf3946e8 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:d8d8686e630b | source=str:7a064df7c74e target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:3d6583e76fac | source=str:ee9886933675 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:03dba354a3dc | source=str:f9f018ac29e0 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:22fafb2fdac1 | source=str:f6ee158f3e4f target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:9a6fb2e69342 | source=str:7a064df7c74e target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:abf493b0a4f1 | source=str:90fecf3946e8 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:a3d65cd3254c | source=str:7cd8821d8d3d target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:c91c4390fba6 | source=str:adbdd7a248ba target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:ec589941c948 | source=str:7a064df7c74e target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:49d2e9dc6f42 | source=str:f6ee158f3e4f target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:8250d5354b90 | source=str:f6ee158f3e4f target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:81a35680a87d | source=str:ee9886933675 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:3cdfc4308d68 | source=str:f6ee158f3e4f target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:dc73be211111 | source=str:f9f018ac29e0 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:17e949419fca | source=str:90fecf3946e8 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:379a0a4436c1 | source=str:f6ee158f3e4f target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:3e5773f0dd55 | source=str:90fecf3946e8 target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:5715f0508235 | source=str:7cd8821d8d3d target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` field_diff: field SIGNUP_DT->signupDt key=tuple:c42ea95b82ce | source=str:7a064df7c74e target=missing | rules=['date_string_to_date!unconverted', 'null_missing_equiv']
- `customerMaster` embed_field_diff: attributes field ATTR_VALUE->v parent=tuple:3c48d54f0eda key=tuple:3950f40cfb74 | source=str:59a984d6e302 target=str:9a7622b24ae7 | rules=[]
- `customerMaster` embed_field_diff: attributes field CREATED_DT->createdDt parent=tuple:3c48d54f0eda key=tuple:3950f40cfb74 | source=str:8bad3ffb6e7f target=datetime:99ff6ec3782d | rules=['date_string_to_date:dby-b3d57e']
- `customerMaster` embed_field_diff: attributes field EAV_ID->eavId parent=tuple:3c48d54f0eda key=tuple:3950f40cfb74 | source=int:b7a56873cd77 target=Int64:25fc0e7096fc | rules=[]
