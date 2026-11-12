# funds parity

Summary: `{'pass': 1800, 'sign-off': 400, 'omitted-optional': 2700, 'responses': 100, 'responsesPassed': 100, 'responsesFailed': 0}`

## 1200137

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "5125.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1200274

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2625.000000"}, {"field": "FUND_UNITS_02", "value": "2625.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1200411

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "1791.488000"}, {"field": "FUND_UNITS_02", "value": "1791.488000"}, {"field": "FUND_UNITS_03", "value": "1792.024000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1200548

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "1375.000000"}, {"field": "FUND_UNITS_02", "value": "1375.000000"}, {"field": "FUND_UNITS_03", "value": "1375.000000"}, {"field": "FUND_UNITS_04", "value": "1375.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1200685

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "1125.000000"}, {"field": "FUND_UNITS_02", "value": "1125.000000"}, {"field": "FUND_UNITS_03", "value": "1125.000000"}, {"field": "FUND_UNITS_04", "value": "1125.000000"}, {"field": "FUND_UNITS_05", "value": "1125.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1200822

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "5750.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1200959

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2937.500000"}, {"field": "FUND_UNITS_02", "value": "2937.500000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1201096

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "1999.800000"}, {"field": "FUND_UNITS_02", "value": "1999.800000"}, {"field": "FUND_UNITS_03", "value": "2000.400000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1201233

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "1531.250000"}, {"field": "FUND_UNITS_02", "value": "1531.250000"}, {"field": "FUND_UNITS_03", "value": "1531.250000"}, {"field": "FUND_UNITS_04", "value": "1531.250000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1201370

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "1250.000000"}, {"field": "FUND_UNITS_02", "value": "1250.000000"}, {"field": "FUND_UNITS_03", "value": "1250.000000"}, {"field": "FUND_UNITS_04", "value": "1250.000000"}, {"field": "FUND_UNITS_05", "value": "1250.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1201507

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "6375.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1201644

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3250.000000"}, {"field": "FUND_UNITS_02", "value": "3250.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1201781

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2208.113000"}, {"field": "FUND_UNITS_02", "value": "2208.113000"}, {"field": "FUND_UNITS_03", "value": "2208.774000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1201918

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "1687.500000"}, {"field": "FUND_UNITS_02", "value": "1687.500000"}, {"field": "FUND_UNITS_03", "value": "1687.500000"}, {"field": "FUND_UNITS_04", "value": "1687.500000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1202055

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "1375.000000"}, {"field": "FUND_UNITS_02", "value": "1375.000000"}, {"field": "FUND_UNITS_03", "value": "1375.000000"}, {"field": "FUND_UNITS_04", "value": "1375.000000"}, {"field": "FUND_UNITS_05", "value": "1375.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1202192

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "7000.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1202329

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3562.500000"}, {"field": "FUND_UNITS_02", "value": "3562.500000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1202466

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2416.425000"}, {"field": "FUND_UNITS_02", "value": "2416.425000"}, {"field": "FUND_UNITS_03", "value": "2417.150000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1202603

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "1843.750000"}, {"field": "FUND_UNITS_02", "value": "1843.750000"}, {"field": "FUND_UNITS_03", "value": "1843.750000"}, {"field": "FUND_UNITS_04", "value": "1843.750000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1202740

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "1500.000000"}, {"field": "FUND_UNITS_02", "value": "1500.000000"}, {"field": "FUND_UNITS_03", "value": "1500.000000"}, {"field": "FUND_UNITS_04", "value": "1500.000000"}, {"field": "FUND_UNITS_05", "value": "1500.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1202877

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "7625.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1203014

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3875.000000"}, {"field": "FUND_UNITS_02", "value": "3875.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1203151

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2624.738000"}, {"field": "FUND_UNITS_02", "value": "2624.738000"}, {"field": "FUND_UNITS_03", "value": "2625.524000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1203288

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2000.000000"}, {"field": "FUND_UNITS_02", "value": "2000.000000"}, {"field": "FUND_UNITS_03", "value": "2000.000000"}, {"field": "FUND_UNITS_04", "value": "2000.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1203425

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "1625.000000"}, {"field": "FUND_UNITS_02", "value": "1625.000000"}, {"field": "FUND_UNITS_03", "value": "1625.000000"}, {"field": "FUND_UNITS_04", "value": "1625.000000"}, {"field": "FUND_UNITS_05", "value": "1625.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1203562

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "8250.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1203699

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "4187.500000"}, {"field": "FUND_UNITS_02", "value": "4187.500000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1203836

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2833.050000"}, {"field": "FUND_UNITS_02", "value": "2833.050000"}, {"field": "FUND_UNITS_03", "value": "2833.900000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1203973

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2156.250000"}, {"field": "FUND_UNITS_02", "value": "2156.250000"}, {"field": "FUND_UNITS_03", "value": "2156.250000"}, {"field": "FUND_UNITS_04", "value": "2156.250000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1204110

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "1750.000000"}, {"field": "FUND_UNITS_02", "value": "1750.000000"}, {"field": "FUND_UNITS_03", "value": "1750.000000"}, {"field": "FUND_UNITS_04", "value": "1750.000000"}, {"field": "FUND_UNITS_05", "value": "1750.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1204247

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "8875.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1204384

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "4500.000000"}, {"field": "FUND_UNITS_02", "value": "4500.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1204521

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3041.363000"}, {"field": "FUND_UNITS_02", "value": "3041.363000"}, {"field": "FUND_UNITS_03", "value": "3042.274000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1204658

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2312.500000"}, {"field": "FUND_UNITS_02", "value": "2312.500000"}, {"field": "FUND_UNITS_03", "value": "2312.500000"}, {"field": "FUND_UNITS_04", "value": "2312.500000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 1204795

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "1875.000000"}, {"field": "FUND_UNITS_02", "value": "1875.000000"}, {"field": "FUND_UNITS_03", "value": "1875.000000"}, {"field": "FUND_UNITS_04", "value": "1875.000000"}, {"field": "FUND_UNITS_05", "value": "1875.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24009756

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "9500.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24010027

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "4812.500000"}, {"field": "FUND_UNITS_02", "value": "4812.500000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24010298

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3249.675000"}, {"field": "FUND_UNITS_02", "value": "3249.675000"}, {"field": "FUND_UNITS_03", "value": "3250.650000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24010569

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2468.750000"}, {"field": "FUND_UNITS_02", "value": "2468.750000"}, {"field": "FUND_UNITS_03", "value": "2468.750000"}, {"field": "FUND_UNITS_04", "value": "2468.750000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24010840

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2000.000000"}, {"field": "FUND_UNITS_02", "value": "2000.000000"}, {"field": "FUND_UNITS_03", "value": "2000.000000"}, {"field": "FUND_UNITS_04", "value": "2000.000000"}, {"field": "FUND_UNITS_05", "value": "2000.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24011111

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "10125.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24011382

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "5125.000000"}, {"field": "FUND_UNITS_02", "value": "5125.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24011653

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3457.988000"}, {"field": "FUND_UNITS_02", "value": "3457.988000"}, {"field": "FUND_UNITS_03", "value": "3459.024000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24011924

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2625.000000"}, {"field": "FUND_UNITS_02", "value": "2625.000000"}, {"field": "FUND_UNITS_03", "value": "2625.000000"}, {"field": "FUND_UNITS_04", "value": "2625.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24012195

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2125.000000"}, {"field": "FUND_UNITS_02", "value": "2125.000000"}, {"field": "FUND_UNITS_03", "value": "2125.000000"}, {"field": "FUND_UNITS_04", "value": "2125.000000"}, {"field": "FUND_UNITS_05", "value": "2125.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24012466

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "10750.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24012737

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "5437.500000"}, {"field": "FUND_UNITS_02", "value": "5437.500000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24013008

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3666.300000"}, {"field": "FUND_UNITS_02", "value": "3666.300000"}, {"field": "FUND_UNITS_03", "value": "3667.400000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24013279

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2781.250000"}, {"field": "FUND_UNITS_02", "value": "2781.250000"}, {"field": "FUND_UNITS_03", "value": "2781.250000"}, {"field": "FUND_UNITS_04", "value": "2781.250000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24013550

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2250.000000"}, {"field": "FUND_UNITS_02", "value": "2250.000000"}, {"field": "FUND_UNITS_03", "value": "2250.000000"}, {"field": "FUND_UNITS_04", "value": "2250.000000"}, {"field": "FUND_UNITS_05", "value": "2250.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24013821

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "11375.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24014092

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "5750.000000"}, {"field": "FUND_UNITS_02", "value": "5750.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24014363

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3874.613000"}, {"field": "FUND_UNITS_02", "value": "3874.613000"}, {"field": "FUND_UNITS_03", "value": "3875.774000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24014634

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2937.500000"}, {"field": "FUND_UNITS_02", "value": "2937.500000"}, {"field": "FUND_UNITS_03", "value": "2937.500000"}, {"field": "FUND_UNITS_04", "value": "2937.500000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24014905

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2375.000000"}, {"field": "FUND_UNITS_02", "value": "2375.000000"}, {"field": "FUND_UNITS_03", "value": "2375.000000"}, {"field": "FUND_UNITS_04", "value": "2375.000000"}, {"field": "FUND_UNITS_05", "value": "2375.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24015176

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "12000.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24015447

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "6062.500000"}, {"field": "FUND_UNITS_02", "value": "6062.500000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24015718

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "4082.925000"}, {"field": "FUND_UNITS_02", "value": "4082.925000"}, {"field": "FUND_UNITS_03", "value": "4084.150000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24015989

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3093.750000"}, {"field": "FUND_UNITS_02", "value": "3093.750000"}, {"field": "FUND_UNITS_03", "value": "3093.750000"}, {"field": "FUND_UNITS_04", "value": "3093.750000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24016260

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2500.000000"}, {"field": "FUND_UNITS_02", "value": "2500.000000"}, {"field": "FUND_UNITS_03", "value": "2500.000000"}, {"field": "FUND_UNITS_04", "value": "2500.000000"}, {"field": "FUND_UNITS_05", "value": "2500.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24016531

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "12625.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24016802

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "6375.000000"}, {"field": "FUND_UNITS_02", "value": "6375.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24017073

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "4291.238000"}, {"field": "FUND_UNITS_02", "value": "4291.238000"}, {"field": "FUND_UNITS_03", "value": "4292.524000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24017344

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3250.000000"}, {"field": "FUND_UNITS_02", "value": "3250.000000"}, {"field": "FUND_UNITS_03", "value": "3250.000000"}, {"field": "FUND_UNITS_04", "value": "3250.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24017615

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2625.000000"}, {"field": "FUND_UNITS_02", "value": "2625.000000"}, {"field": "FUND_UNITS_03", "value": "2625.000000"}, {"field": "FUND_UNITS_04", "value": "2625.000000"}, {"field": "FUND_UNITS_05", "value": "2625.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24017886

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "13250.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24018157

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "6687.500000"}, {"field": "FUND_UNITS_02", "value": "6687.500000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24018428

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "4499.550000"}, {"field": "FUND_UNITS_02", "value": "4499.550000"}, {"field": "FUND_UNITS_03", "value": "4500.900000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24018699

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3406.250000"}, {"field": "FUND_UNITS_02", "value": "3406.250000"}, {"field": "FUND_UNITS_03", "value": "3406.250000"}, {"field": "FUND_UNITS_04", "value": "3406.250000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 24018970

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2750.000000"}, {"field": "FUND_UNITS_02", "value": "2750.000000"}, {"field": "FUND_UNITS_03", "value": "2750.000000"}, {"field": "FUND_UNITS_04", "value": "2750.000000"}, {"field": "FUND_UNITS_05", "value": "2750.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360027619

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "13875.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360028008

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "7000.000000"}, {"field": "FUND_UNITS_02", "value": "7000.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360028397

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "4707.863000"}, {"field": "FUND_UNITS_02", "value": "4707.863000"}, {"field": "FUND_UNITS_03", "value": "4709.274000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360028786

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3562.500000"}, {"field": "FUND_UNITS_02", "value": "3562.500000"}, {"field": "FUND_UNITS_03", "value": "3562.500000"}, {"field": "FUND_UNITS_04", "value": "3562.500000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360029175

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "2875.000000"}, {"field": "FUND_UNITS_02", "value": "2875.000000"}, {"field": "FUND_UNITS_03", "value": "2875.000000"}, {"field": "FUND_UNITS_04", "value": "2875.000000"}, {"field": "FUND_UNITS_05", "value": "2875.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360029564

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "14500.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360029953

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "7312.500000"}, {"field": "FUND_UNITS_02", "value": "7312.500000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360030342

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "4916.175000"}, {"field": "FUND_UNITS_02", "value": "4916.175000"}, {"field": "FUND_UNITS_03", "value": "4917.650000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360030731

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3718.750000"}, {"field": "FUND_UNITS_02", "value": "3718.750000"}, {"field": "FUND_UNITS_03", "value": "3718.750000"}, {"field": "FUND_UNITS_04", "value": "3718.750000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360031120

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3000.000000"}, {"field": "FUND_UNITS_02", "value": "3000.000000"}, {"field": "FUND_UNITS_03", "value": "3000.000000"}, {"field": "FUND_UNITS_04", "value": "3000.000000"}, {"field": "FUND_UNITS_05", "value": "3000.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360031509

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "15125.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360031898

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "7625.000000"}, {"field": "FUND_UNITS_02", "value": "7625.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360032287

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "5124.488000"}, {"field": "FUND_UNITS_02", "value": "5124.488000"}, {"field": "FUND_UNITS_03", "value": "5126.024000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360032676

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3875.000000"}, {"field": "FUND_UNITS_02", "value": "3875.000000"}, {"field": "FUND_UNITS_03", "value": "3875.000000"}, {"field": "FUND_UNITS_04", "value": "3875.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360033065

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3125.000000"}, {"field": "FUND_UNITS_02", "value": "3125.000000"}, {"field": "FUND_UNITS_03", "value": "3125.000000"}, {"field": "FUND_UNITS_04", "value": "3125.000000"}, {"field": "FUND_UNITS_05", "value": "3125.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360033454

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "15750.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360033843

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "7937.500000"}, {"field": "FUND_UNITS_02", "value": "7937.500000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360034232

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "5332.800000"}, {"field": "FUND_UNITS_02", "value": "5332.800000"}, {"field": "FUND_UNITS_03", "value": "5334.400000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360034621

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "4031.250000"}, {"field": "FUND_UNITS_02", "value": "4031.250000"}, {"field": "FUND_UNITS_03", "value": "4031.250000"}, {"field": "FUND_UNITS_04", "value": "4031.250000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360035010

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3250.000000"}, {"field": "FUND_UNITS_02", "value": "3250.000000"}, {"field": "FUND_UNITS_03", "value": "3250.000000"}, {"field": "FUND_UNITS_04", "value": "3250.000000"}, {"field": "FUND_UNITS_05", "value": "3250.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360035399

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "16375.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360035788

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "8250.000000"}, {"field": "FUND_UNITS_02", "value": "8250.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360036177

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "5541.113000"}, {"field": "FUND_UNITS_02", "value": "5541.113000"}, {"field": "FUND_UNITS_03", "value": "5542.774000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360036566

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "4187.500000"}, {"field": "FUND_UNITS_02", "value": "4187.500000"}, {"field": "FUND_UNITS_03", "value": "4187.500000"}, {"field": "FUND_UNITS_04", "value": "4187.500000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 360036955

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3375.000000"}, {"field": "FUND_UNITS_02", "value": "3375.000000"}, {"field": "FUND_UNITS_03", "value": "3375.000000"}, {"field": "FUND_UNITS_04", "value": "3375.000000"}, {"field": "FUND_UNITS_05", "value": "3375.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 4700048288

Counts: `{'pass': 10, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "17000.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "100.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 4700048791

Counts: `{'pass': 14, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "8562.500000"}, {"field": "FUND_UNITS_02", "value": "8562.500000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "50.00"}, {"field": "ALLOC_PCT_02", "value": "50.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 4700049294

Counts: `{'pass': 18, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "5749.425000"}, {"field": "FUND_UNITS_02", "value": "5749.425000"}, {"field": "FUND_UNITS_03", "value": "5751.150000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "33.33"}, {"field": "ALLOC_PCT_02", "value": "33.33"}, {"field": "ALLOC_PCT_03", "value": "33.34"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 4700049797

Counts: `{'pass': 22, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "4343.750000"}, {"field": "FUND_UNITS_02", "value": "4343.750000"}, {"field": "FUND_UNITS_03", "value": "4343.750000"}, {"field": "FUND_UNITS_04", "value": "4343.750000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "25.00"}, {"field": "ALLOC_PCT_02", "value": "25.00"}, {"field": "ALLOC_PCT_03", "value": "25.00"}, {"field": "ALLOC_PCT_04", "value": "25.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

## 4700050300

Counts: `{'pass': 26, 'sign-off': 4, 'omitted-optional': 27}`

- {"field": "FUND_UNITS_NN", "iri": "funds[].fundSegments[0].numberOfUnits", "result": "sign-off", "note": "Proposed segment; creating it also requires segmentId, fundId, originalDepositAmount, originalDepositDate, depositDate, depositAmount, currentAmount, renewalDate, sweepAccountId, startDate and endDate.", "transformed": [{"field": "FUND_UNITS_01", "value": "3500.000000"}, {"field": "FUND_UNITS_02", "value": "3500.000000"}, {"field": "FUND_UNITS_03", "value": "3500.000000"}, {"field": "FUND_UNITS_04", "value": "3500.000000"}, {"field": "FUND_UNITS_05", "value": "3500.000000"}]}
- {"field": "ALLOC_PCT_NN", "iri": "none", "result": "sign-off", "note": "No PolicyFunds element.", "transformed": [{"field": "ALLOC_PCT_01", "value": "20.00"}, {"field": "ALLOC_PCT_02", "value": "20.00"}, {"field": "ALLOC_PCT_03", "value": "20.00"}, {"field": "ALLOC_PCT_04", "value": "20.00"}, {"field": "ALLOC_PCT_05", "value": "20.00"}]}
- {"field": "none", "iri": "funds[].fundValuationDate", "result": "sign-off", "note": "Cross-table source absent from flat legacy funds response; query by contract.", "transformed": []}
- {"field": "none", "iri": "funds[].fundAccountType", "result": "sign-off", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.fundRestrictReason", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo.endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.indexReturnPercent", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.tieredRate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateTier.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].segmentId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].fundId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].originalDepositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].depositAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].currentAmount", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].renewalDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].numberOfUnits", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].sweepAccountId", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].startDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].fundSegments[].endDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.rateType", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockStartDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo.lockEndDate", "result": "omitted-optional", "note": "Required by schema; no direct legacy source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferSendRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferSendAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].transferDestRestrictInfo", "result": "omitted-optional", "note": "Required when isTransferDestAllowed=false; no source.", "transformed": []}
- {"field": "none", "iri": "funds[].rateLockInfo", "result": "omitted-optional", "note": "Required when isLockFeatureEnabled=true; no source.", "transformed": []}

