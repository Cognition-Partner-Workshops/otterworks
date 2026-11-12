# Policy Inquiry lineage

Generated from `lineage.yaml`; edit the YAML, not this table.

## summary

| DB column | legacy field (format) | IRI element (type/constraint) | rule | status | sign-off |
| --- | --- | --- | --- | --- | --- |
| annuity_policy.CONTRACT_NO | CNTR_NO (digits, no padding) | path:policyNumber (string) | contract_number | mapped | — |
| annuity_policy.STATUS_CODE | STAT_CD (code) | /policyStatus (IRI policyStatus enum) | enum_map IF→ACTIVE, PI→PENDINGISSUED, LP→LAPSED, SR→SURRENDERED, TM→TERMINATED, DP→None | signoff | S-02 |
| annuity_policy.PRODUCT_NAME | PROD_NM (string) | /product/planName (string) | identity | mapped | — |
| annuity_policy.PLAN_CODE | PLAN_CD (string) | /product/planCode (string ^[A-Za-z0-9]{1,50}$) | identity | provisional | S-07 |
| annuity_policy.PRODUCT_CODE | PROD_CD (string) | — (string) | dropped | dropped | S-07 |
| annuity_policy.PLAN_CODE | PLAN_CD (code) | /product/productType (IRI productType enum) | enum_map FIXED→FIXED, FLEX→DEFERRED | provisional | S-06 |
| annuity_policy.QUALIFICATION_CODE | QUAL_CD (code) | /qualificationType (IRI qualificationType enum) | enum_map NQ→Non-Qualified, IRA→IRA, ROTH→Roth IRA | mapped | S-08 |
| annuity_policy.ISSUE_STATE | ISS_ST (string) | /issueState (string ^[A-Z]{2}$) | identity | mapped | — |
| annuity_policy.CURRENCY_CODE | CCY_CD (string) | /currency (string ^[A-Z]{3}$) | identity | mapped | — |
| annuity_policy.EFFECTIVE_DATE | EFF_DT (YYYYMMDD) | /effectiveDate (string date) | yyyymmdd_to_date | mapped | — |
| annuity_policy.ISSUE_DATE | ISS_DT (YYYYMMDD) | — (string) | dropped | dropped | S-09 |
| annuity_policy.MATURITY_DATE | MAT_DT (YYYYMMDD) | — (string) | dropped | dropped | S-09 |
| annuity_policy.OWNER_NAME | OWN_NM (string) | — (string) | dropped | dropped | S-09 |
| annuity_policy.ANNUITANT_NAME | ANN_NM (string) | — (string) | dropped | dropped | S-09 |
| annuity_policy.GRX_IND | GRX_IND (string) | — (string) | dropped | signoff | S-01 |
| — | no source (none) | /carrierId (string) | provisional | provisional | S-03 |
| — | no source (none) | /issueType (string) | provisional | provisional | S-04 |
| — | no source (none) | /policyLastRefreshDateTime (string date-time) | provisional | provisional | S-05 |
| — | RTN_CD (two digits) | HTTP status (HTTP status) | enum_map 00→200, 04→404, 08→400, 96→503 | mapped | — |

- `CNTR_NO`: C-2: policyNumber is a path parameter only.
- `STAT_CD`: IRI-02: DP has no IRI value; return 422 policy.status.unmapped.
- `PLAN_CD`: PLAN_CODE passes the constraint; PRODUCT_CODE ANN-1 does not.
- `PROD_CD`: Not a valid IRI planCode.
- `PLAN_CD`: Provisional product type mapping.
- `QUAL_CD`: Confirm qualification mapping.
- `ISS_DT`: Belongs to getPolicyDates, out of scope.
- `MAT_DT`: Belongs to getPolicyDates, out of scope.
- `OWN_NM`: Belongs to getPolicyParties, out of scope.
- `ANN_NM`: Belongs to getPolicyParties, out of scope.
- `GRX_IND`: IRI-04: unexplained field, no IRI element; not emitted until a business owner decides.
- `/carrierId`: Config value SYNANN.
- `/issueType`: Config value GUARANTEED.
- `/policyLastRefreshDateTime`: Response time, UTC.
- `RTN_CD`: 00->200; 04->404 policy.inquiry.notFound; 08->400 policy.inquiry.invalidPolicyNumber; 96->503 policy.inquiry.unavailable.

## values

| DB column | legacy field (format) | IRI element (type/constraint) | rule | status | sign-off |
| --- | --- | --- | --- | --- | --- |
| policy_values.CONTRACT_NO | CNTR_NO (10-digit zero padded) | path:policyNumber (string) | contract_number | mapped | — |
| policy_values.VALUATION_DATE | VAL_DT (YYYYMMDD) | /valuesAsOfDate (string date) | yyyymmdd_to_date | mapped | — |
| policy_values.ACCOUNT_VALUE | ACCT_VAL (15 digits, implied scale 2) | /accountValues/endingAccountValue (number) | implied_decimal(2) | mapped | — |
| policy_values.SURRENDER_VALUE | SURR_VAL (15 digits, implied scale 2) | /accountValues/surrenderValue (number) | implied_decimal(2) | mapped | — |
| policy_values.PREMIUMS_TO_DATE | PREM_TD (15 digits, implied scale 2) | /totalDepositITD (number) | implied_decimal(2) | mapped | — |
| policy_values.WITHDRAWALS_TO_DATE | WDR_TD (15 digits, implied scale 2) | /accountValues/totalNetWithdrawalSinceIssue (number) | implied_decimal(2) | provisional | S-12 |
| policy_values.CASH_VALUE | CASH_VAL (15 digits, implied scale 2) | — (string) | dropped | dropped | S-10 |
| policy_values.DEATH_BENEFIT | DTH_BEN (15 digits, implied scale 2) | — (string) | dropped | dropped | S-11 |
| policy_values.SURRENDER_CHARGE | SURR_CHG (15 digits, implied scale 2) | — (string) | dropped | dropped | S-11 |
| — | RTN_CD (two digits) | HTTP status (HTTP status) | enum_map 00→200, 04→404, 08→400, 96→503 | mapped | — |

- `CNTR_NO`: IRI-01: canonicalize padded values contract number; C-2: never echo policyNumber in body.
- `ACCT_VAL`: IRI-03.
- `SURR_VAL`: IRI-03.
- `PREM_TD`: IRI-03.
- `WDR_TD`: provisional-semantics: confirm gross vs net.
- `CASH_VAL`: guaranteedCashSurrenderValue* are guaranteed values, not current cash value.
- `DTH_BEN`: No PolicyValue element.
- `SURR_CHG`: No PolicyValue element.
- `RTN_CD`: 00->200; 04->404 policy.inquiry.notFound; 08->400 policy.inquiry.invalidPolicyNumber; 96->503 policy.inquiry.unavailable.

## funds

| DB column | legacy field (format) | IRI element (type/constraint) | rule | status | sign-off |
| --- | --- | --- | --- | --- | --- |
| fund_allocation.CONTRACT_NO | CNTR_NO (digits, no padding) | path:policyNumber (string) | contract_number | mapped | — |
| — | FUND_CNT (integer digits) | /itemsCount, /totalItemsCount (integer) | count | mapped | — |
| fund_allocation.FUND_CODE | FUND_CD_nn (string) | /funds/i/fundId (string) | indexed_list / identity | mapped | — |
| fund_allocation.FUND_NAME | FUND_NM_nn (string) | /funds/i/fundName (string) | indexed_list / identity | mapped | — |
| fund_allocation.UNIT_VALUE | UNIT_VAL_nn (digits, implied scale 6) | /funds/i/fundPrice (number) | indexed_list(6) / implied_decimal | mapped | — |
| fund_allocation.FUND_VALUE | FUND_VAL_nn (digits, implied scale 2) | /funds/i/totalFundValue (number) | indexed_list(2) / implied_decimal | mapped | — |
| fund_allocation.ALLOCATION_PCT | ALLOC_PCT_nn (indexed implied decimal) | — (string) | dropped | dropped | S-15 |
| fund_allocation.FUND_UNITS | FUND_UNITS_nn (indexed implied decimal) | — (string) | dropped | dropped | S-16 |
| — | no source (none) | /funds/i/fundAccountType (IRI fundAccountType enum) | provisional | provisional | S-13 |
| — | no source (none) | /funds/i/fundValuationDate (string date) | provisional | provisional | S-14 |
| — | RTN_CD (two digits) | HTTP status (HTTP status) | enum_map 00→200, 04→404, 08→400, 96→503 | mapped | — |

- `CNTR_NO`: C-2: policyNumber is a path parameter only.
- `FUND_CNT`: Also totalItemsCount; startIndex 0 when no paging parameters.
- `FUND_CD_nn`: Ordered by fund_code; suffix _01.._NN.
- `FUND_NM_nn`: Ordered by fund_code; suffix _01.._NN.
- `UNIT_VAL_nn`: Ordered by fund_code; suffix _01.._NN.
- `FUND_VAL_nn`: Ordered by fund_code; suffix _01.._NN.
- `ALLOC_PCT_nn`: No allocation element in PolicyFunds.
- `FUND_UNITS_nn`: Only home is fundSegments[].numberOfUnits whose 12 required siblings have no source.
- `/funds/i/fundAccountType`: Config value OTHER.
- `/funds/i/fundValuationDate`: Source policy_values.valuation_date for the contract.
- `RTN_CD`: 00->200; 04->404 policy.inquiry.notFound; 08->400 policy.inquiry.invalidPolicyNumber; 96->503 policy.inquiry.unavailable; legacy 404 when no fund rows.

## IRI required elements with no legacy source

- summary `/carrierId`: Config value SYNANN (S-03).
- summary `/issueType`: Config value GUARANTEED (S-04).
- summary `/policyLastRefreshDateTime`: Response time, UTC (S-05).
- funds `/funds/i/fundAccountType`: Config value OTHER (S-13).
- funds `/funds/i/fundValuationDate`: Source policy_values.valuation_date for the contract (S-14).

## Sign-off list

- **S-01**: IRI-04: unexplained field, no IRI element; not emitted until a business owner decides.
- **S-02**: IRI-02: DP has no IRI value; return 422 policy.status.unmapped.
- **S-03**: Config value SYNANN.
- **S-04**: Config value GUARANTEED.
- **S-05**: Response time, UTC.
- **S-06**: Provisional product type mapping.
- **S-07**: PLAN_CODE passes the constraint; PRODUCT_CODE ANN-1 does not; Not a valid IRI planCode.
- **S-08**: Confirm qualification mapping.
- **S-09**: Belongs to getPolicyDates, out of scope; Belongs to getPolicyParties, out of scope.
- **S-10**: guaranteedCashSurrenderValue* are guaranteed values, not current cash value.
- **S-11**: No PolicyValue element.
- **S-12**: provisional-semantics: confirm gross vs net.
- **S-13**: Config value OTHER.
- **S-14**: Source policy_values.valuation_date for the contract.
- **S-15**: No allocation element in PolicyFunds.
- **S-16**: Only home is fundSegments[].numberOfUnits whose 12 required siblings have no source.
