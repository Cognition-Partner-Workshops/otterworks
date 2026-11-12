# values sign-off list (business owner)

Operation `getPolicyValue` (`GET /v1/policies/{policyNumber}/values`). Live parity: 100/100
responses pass (700 fields pass, 400 sign-off, 500 omitted-optional, 0 fail). Schema: 101/101
(100 frozen contracts + 404). Every sign-off field below is emitted in all 100 payloads and equals
the frozen legacy value (400/400 checked); none are counted as passes.

| # | Legacy | Oracle column | Current IRI payload | Decision needed |
| --- | --- | --- | --- | --- |
| 1 | WDR_TD | POLICY_VALUES.WITHDRAWALS_TO_DATE | `accountValues.totalNetWithdrawalSinceIssue` | Is WITHDRAWALS_TO_DATE net (after charges/tax) or gross? If gross, which IRI element (if any) should carry it. |
| 2 | CASH_VAL | POLICY_VALUES.CASH_VALUE | `legacyUnmappedValues.cashValue` (extension) | No PolicyValue element. Equals SURR_VAL in all 100 records; confirm a target element (e.g. a guaranteedCashSurrenderValue* field) or that the extension is acceptable/droppable. |
| 3 | DTH_BEN | POLICY_VALUES.DEATH_BENEFIT | `legacyUnmappedValues.deathBenefit` (extension) | No PolicyValue element; confirm target (another IRI operation, e.g. riders) or extension. |
| 4 | SURR_CHG | POLICY_VALUES.SURRENDER_CHARGE | `legacyUnmappedValues.surrenderCharge` (extension) | No PolicyValue element; ACCT_VAL - SURR_VAL = SURR_CHG in all 100 records. Confirm target or extension. |

`legacyUnmappedValues` is a provisional, schema-valid extension (PolicyValue is an open object) so
legacy data is not silently dropped; its name and placement are part of decisions 2-4.

Omitted-optional (not sign-off, no legacy source): `withdrawalValues` (required child
`yearToDateFreeWithdrawalAmount`) and `authorization` (required `businessMethods`,
`authorizationEntities`, `authorizationTransaction.administrativeTransactions`).

Error mapping: RTN_CD 04 -> 404 `Inquiry.Request.NotFound`, 08 -> 400 `Inquiry.Request.Invalid`
(non-digit or >30-char policyNumber, out-of-range amount as in legacy), 96 -> 503
`Inquiry.Request.Unavailable` (verified live with Oracle stopped).
