# IRI Policy Inquiry lineage

Generated from lineage.yaml; do not edit this document.

## Rules

- **identity**: `{'kind': 'identity'}`
- **status**: `{'kind': 'status'}`
- **policy-number**: `{'kind': 'integer'}`
- **date**: `{'kind': 'date', 'input': 'YYYYMMDD', 'output': 'YYYY-MM-DD'}`
- **decimal-2**: `{'kind': 'decimal', 'scale': 2}`
- **decimal-6**: `{'kind': 'decimal', 'scale': 6}`
- **integer**: `{'kind': 'integer'}`
- **policy-status**: `{'kind': 'enum', 'values': {'IF': 'ACTIVE', 'LP': 'LAPSED', 'SR': 'SURRENDERED', 'TM': 'TERMINATED', 'PI': 'PENDINGISSUED'}}`
- **qualification**: `{'kind': 'enum', 'values': {'NQ': 'Non-Qualified', 'IRA': 'IRA', 'ROTH': 'Roth IRA'}}`
- **page-count**: `{'kind': 'page-count'}`
- **page-start**: `{'kind': 'page-start'}`
- **config**: `{'kind': 'config'}`
- **container**: `{'kind': 'container'}`
- **unresolved**: `{'kind': 'unresolved'}`

RTN_CD / HTTP: 00 → 200, 04 → 404, 08 → 400, 96 → 503
Errors use the pinned Error schema (code, message; timestamp optional; correlationId header only).

## summary

| DB column → legacy field → IRI element | Rule | Status | Note |
| --- | --- | --- | --- |
| none → RTN_CD (two digit code) → $status | status | mapped |  |
| ANNUITY_POLICY.CONTRACT_NO → CNTR_NO (unpadded digits) → $request.policyNumber | policy-number | derived | Path parameter, not a response property; compare numerically. |
| ANNUITY_POLICY.STATUS_CODE → STAT_CD (string code/text) → policyStatus | policy-status | mapped | PI is inferred and DP has no enum; conditional sign-off rows below. |
| ANNUITY_POLICY.PRODUCT_NAME → PROD_NM (string code/text) → product.planName | identity | mapped |  |
| ANNUITY_POLICY.PLAN_CODE → PLAN_CD (string code/text) → product.planCode | identity | mapped | FIXED/FLEX is not productType. |
| ANNUITY_POLICY.PRODUCT_CODE → PROD_CD (string code/text) → product.shortName | identity | sign-off | Proposed shortName; confirm business semantics. |
| ANNUITY_POLICY.QUALIFICATION_CODE → QUAL_CD (string code/text) → qualificationType | qualification | mapped |  |
| ANNUITY_POLICY.EFFECTIVE_DATE → EFF_DT (YYYYMMDD) → effectiveDate | date | mapped |  |
| ANNUITY_POLICY.ISSUE_STATE → ISS_ST (string code/text) → issueState | identity | mapped |  |
| ANNUITY_POLICY.CURRENCY_CODE → CCY_CD (string code/text) → currency | identity | mapped |  |
| ANNUITY_POLICY.ISSUE_DATE → ISS_DT (YYYYMMDD) → none | date | not-in-operation | Belongs to /dates. |
| ANNUITY_POLICY.MATURITY_DATE → MAT_DT (YYYYMMDD) → none | date | not-in-operation | Belongs to /dates. |
| ANNUITY_POLICY.OWNER_NAME → OWN_NM (string code/text) → none | identity | not-in-operation | Belongs to /parties. |
| ANNUITY_POLICY.ANNUITANT_NAME → ANN_NM (string code/text) → none | identity | not-in-operation | Belongs to /parties. |
| ANNUITY_POLICY.GRX_IND → GRX_IND (string code/text) → none | identity | sign-off | Undocumented codes 0/1/3; retain field pending decision. |
| ANNUITY_POLICY.STATUS_CODE → STAT_CD (two character code) → policyStatus | policy-status | sign-off | PI -> PENDINGISSUED inferred; confirm. |
| ANNUITY_POLICY.STATUS_CODE → STAT_CD (two character code) → policyStatus | policy-status | sign-off | No IRI enum; do not silently drop or invent an enum. |
| none → none (config string) → carrierId | config | sign-off | Constant from IRI_CARRIER_ID; value requires sign-off. |
| none → none (config string) → carrierName | config | sign-off | Constant from IRI_CARRIER_NAME; value requires sign-off. |
| none → none (none) → policyLastRefreshDateTime | unresolved | sign-off | Required by schema; no direct legacy source. |
| none → none (object) → product | container | derived | Assemble child fields; required when parent is present. |
| none → none (none) → product.productType | unresolved | sign-off | Required by schema; no direct legacy source. |
| none → none (none) → restrictions[].category | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → restrictions[].subCategory | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → restrictions[].reason | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → restrictions[].definition | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → issueType | unresolved | sign-off | Required by schema; no direct legacy source. |
| none → none (object) → restrictions | unresolved | omitted-optional | Required with at least one item when hasRestriction=true; no source. |
| none → none (none) → hasRestriction | unresolved | omitted-optional | Optional restriction indicator has no source; omit it and restrictions. |

## values

| DB column → legacy field → IRI element | Rule | Status | Note |
| --- | --- | --- | --- |
| none → RTN_CD (two digit code) → $status | status | mapped |  |
| POLICY_VALUES.CONTRACT_NO → CNTR_NO (10 zero-padded digits) → $request.policyNumber | policy-number | derived | Path parameter, not a response property; compare numerically. |
| POLICY_VALUES.VALUATION_DATE → VAL_DT (YYYYMMDD) → valuesAsOfDate | date | mapped |  |
| POLICY_VALUES.ACCOUNT_VALUE → ACCT_VAL (15 digits implied scale 2) → accountValues.endingAccountValue | decimal-2 | mapped |  |
| POLICY_VALUES.SURRENDER_VALUE → SURR_VAL (15 digits implied scale 2) → accountValues.surrenderValue | decimal-2 | mapped |  |
| POLICY_VALUES.PREMIUMS_TO_DATE → PREM_TD (15 digits implied scale 2) → totalDepositITD | decimal-2 | mapped |  |
| POLICY_VALUES.WITHDRAWALS_TO_DATE → WDR_TD (15 digits implied scale 2) → accountValues.totalNetWithdrawalSinceIssue | decimal-2 | sign-off | Confirm net versus gross. |
| POLICY_VALUES.CASH_VALUE → CASH_VAL (15 digits implied scale 2) → none | decimal-2 | sign-off | No PolicyValue element. |
| POLICY_VALUES.DEATH_BENEFIT → DTH_BEN (15 digits implied scale 2) → none | decimal-2 | sign-off | No PolicyValue element. |
| POLICY_VALUES.SURRENDER_CHARGE → SURR_CHG (15 digits implied scale 2) → none | decimal-2 | sign-off | No PolicyValue element. |
| none → none (none) → withdrawalValues.yearToDateFreeWithdrawalAmount | unresolved | omitted-optional | Required if withdrawalValues present; omit optional parent, not fabricate a value. |
| none → none (object) → accountValues | container | derived | Assemble child fields; required when parent is present. |
| none → none (object) → authorization.businessMethods | container | omitted-optional | Required only when optional parent is present; no source, omit optional parent. |
| none → none (object) → authorization.authorizationEntities | container | omitted-optional | Required only when optional parent is present; no source, omit optional parent. |
| none → none (object) → authorization.authorizationTransaction | container | omitted-optional | Required only when optional parent is present; no source, omit optional parent. |
| none → none (object) → authorization.authorizationTransaction.administrativeTransactions | container | omitted-optional | Required only when optional parent is present; no source, omit optional parent. |

## funds

| DB column → legacy field → IRI element | Rule | Status | Note |
| --- | --- | --- | --- |
| none → RTN_CD (two digit code) → $status | status | mapped |  |
| FUND_ALLOCATION.CONTRACT_NO → CNTR_NO (unpadded digits) → $request.policyNumber | policy-number | derived | Path parameter, not a response property; compare numerically. |
| none → FUND_CNT (unpadded integer) → totalItemsCount | integer | derived | Count before paging. |
| none → FUND_CNT (unpadded integer) → itemsCount | page-count | derived | Count after startIndex/limit; default 50, max 200. |
| none → none (request integer) → startIndex | page-start | derived | Default 0; preserve ORDER BY fund_code. |
| FUND_ALLOCATION.FUND_CODE → FUND_CD_NN (string) → funds[].fundId | identity | mapped |  |
| FUND_ALLOCATION.FUND_NAME → FUND_NM_NN (string) → funds[].fundName | identity | mapped |  |
| FUND_ALLOCATION.UNIT_VALUE → UNIT_VAL_NN (15 digits implied scale 6) → funds[].fundPrice | decimal-6 | mapped |  |
| FUND_ALLOCATION.FUND_VALUE → FUND_VAL_NN (15 digits implied scale 2) → funds[].totalFundValue | decimal-2 | mapped |  |
| FUND_ALLOCATION.FUND_UNITS → FUND_UNITS_NN (18 digits implied scale 6) → funds[].fundSegments[0].numberOfUnits | decimal-6 | sign-off | Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate. |
| FUND_ALLOCATION.ALLOCATION_PCT → ALLOC_PCT_NN (5 digits implied scale 2) → none | decimal-2 | sign-off | No PolicyFunds element. |
| POLICY_VALUES.VALUATION_DATE → none (Oracle DATE) → funds[].fundValuationDate | date | sign-off | Cross-table source absent from flat legacy funds response; query by contract. |
| none → none (none) → funds[].fundAccountType | unresolved | sign-off | Required by schema; no direct legacy source. |
| none → none (none) → funds[].transferSendRestrictInfo.fundRestrictReason | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].transferSendRestrictInfo.startDate | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].transferSendRestrictInfo.endDate | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].transferDestRestrictInfo.fundRestrictReason | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].transferDestRestrictInfo.startDate | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].transferDestRestrictInfo.endDate | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].rateTier.indexReturnPercent | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].rateTier.tieredRate | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].rateTier.rateType | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].fundSegments[].segmentId | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].fundSegments[].fundId | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].fundSegments[].originalDepositAmount | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].fundSegments[].originalDepositDate | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].fundSegments[].depositDate | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].fundSegments[].depositAmount | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].fundSegments[].currentAmount | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].fundSegments[].renewalDate | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].fundSegments[].numberOfUnits | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].fundSegments[].sweepAccountId | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].fundSegments[].startDate | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].fundSegments[].endDate | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].rateLockInfo.rateType | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].rateLockInfo.lockStartDate | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (none) → funds[].rateLockInfo.lockEndDate | unresolved | omitted-optional | Required by schema; no direct legacy source. |
| none → none (object) → funds[].transferSendRestrictInfo | unresolved | omitted-optional | Required when isTransferSendAllowed=false; no source. |
| none → none (object) → funds[].transferDestRestrictInfo | unresolved | omitted-optional | Required when isTransferDestAllowed=false; no source. |
| none → none (object) → funds[].rateLockInfo | unresolved | omitted-optional | Required when isLockFeatureEnabled=true; no source. |

## Sign-off

A difference is a failure until explained from data. Business-only decisions belong here; the field stays in the payload.

- **summary: PROD_CD → product.shortName**: Proposed shortName; confirm business semantics.
- **summary: GRX_IND → none**: Undocumented codes 0/1/3; retain field pending decision.
- **summary: STAT_CD → policyStatus**: PI -> PENDINGISSUED inferred; confirm.
- **summary: STAT_CD → policyStatus**: No IRI enum; do not silently drop or invent an enum.
- **summary: none → carrierId**: Constant from IRI_CARRIER_ID; value requires sign-off.
- **summary: none → carrierName**: Constant from IRI_CARRIER_NAME; value requires sign-off.
- **values: WDR_TD → accountValues.totalNetWithdrawalSinceIssue**: Confirm net versus gross.
- **values: CASH_VAL → none**: No PolicyValue element.
- **values: DTH_BEN → none**: No PolicyValue element.
- **values: SURR_CHG → none**: No PolicyValue element.
- **funds: FUND_UNITS_NN → funds[].fundSegments[0].numberOfUnits**: Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.
- **funds: ALLOC_PCT_NN → none**: No PolicyFunds element.
- **funds: none → funds[].fundValuationDate**: Cross-table source absent from flat legacy funds response; query by contract.
- **summary: none → policyLastRefreshDateTime**: Required by schema; no direct legacy source.
- **summary: none → product.productType**: Required by schema; no direct legacy source.
- **summary: none → issueType**: Required by schema; no direct legacy source.
- **funds: none → funds[].fundAccountType**: Required by schema; no direct legacy source.
