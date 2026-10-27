# Global fleet: rule coverage and legacy parity

Verified on `integration/global-fleet` at `8960d8319` (the PR #2280 merge, after #2284 at `6a0d8c74c`), local runs on 2026-10-27. There is no test CI on this branch; the output below is from local runs. No application code was changed for this report. The only code added is the UK replay runner `src/test/java/com/otterworks/fleet/verification/HoldoutCandidate.java`.

Result in one line: **34/34 rules covered and passing in uk, de and the frontend.** In the UK holdouts, every difference is one of the expected GF29 changes (198 overlap records and 41 pool-loan records), but `check_pairs.py --candidate` still exits 1 because fleet-service writes no `BENRPT.txt` (D1). **The DE corpus shows three defects (D2-D4)** on top of the expected GF21 changes.

## 1. Test gates

| Gate | Command (from `fleet-service`, Maven Central mirror via `-s settings.xml`) | Result |
|---|---|---|
| UK | `./mvnw -B clean verify -Puk` | BUILD SUCCESS; surefire 65 run, 0 failures, 0 errors, 0 skipped; failsafe `PackagedJarBootIT` 1 run, 0 failures |
| DE | `./mvnw -B verify -Pde` | BUILD SUCCESS; surefire 65 run, 0 failures, 0 errors, 0 skipped; failsafe `PackagedJarBootIT` 1 run, 0 failures |
| Frontend | `npm ci && npm run build && npm test` (`frontend/fleet`) | build OK; 7 files, 39 tests passed, 0 failed |
| Coverage | `python3 ../scripts/rule_coverage.py --junit uk=<surefire+failsafe uk> --junit de=<surefire+failsafe de> --vitest ../frontend/fleet/reports/vitest-junit.xml` | exit 0; covered 34/34, partial -, failed -, missing - |

The surefire and failsafe XML files for each country were combined into one directory per `--junit` input, so `PackagedJarBootIT` counts in both profiles.

### Coverage (every `tests[].name` in `discovery/catalog.json`, exact names)

| Rule | Test | Layer | uk | de | vitest |
|---|---|---|---|---|---|
| GF01 | GF01_countryParametersComeFromProfile | fleet-service | passed | passed | n/a |
| GF01 | GF01_noCountryNameInConditionals | extra | passed | passed | n/a |
| GF02 | GF02_gradeBelowThresholdIsRefused | fleet-service | passed | passed | n/a |
| GF02 | GF02_gradeAtThresholdIsEligible | fleet-service | passed | passed | n/a |
| GF02 | GF02_batchRunListsBelowThresholdHolders | fleet-service | passed | passed | n/a |
| GF02 | GF02_invalidBatchPeriodReturnsBadRequest | extra | passed | passed | n/a |
| GF03 | GF03_unknownEmployeeIsRejected | fleet-service | passed | passed | n/a |
| GF03 | GF03_employeeStatusGatesCarRequest | fleet-service | passed | passed | n/a |
| GF03 | GF03_inquiryPageShowsLeaver | extra | n/a | n/a | passed |
| GF03 | GF03_inquiryPageShowsNotFound | extra | n/a | n/a | passed |
| GF03 | GF03_leaverMayClaimUpToLeavingDate | extra | passed | passed | n/a |
| GF04 | GF04_rehireEmploymentsAreKeptApart | fleet-service | passed | passed | n/a |
| GF04 | GF04_migrationKeepsNamesAndBackfillsStatus | extra | passed | passed | n/a |
| GF05 | GF05_secondOpenCarIsRefused | fleet-service | passed | passed | n/a |
| GF05 | GF05_unconfirmedDoubleHoldersBlockCutover | fleet-service | passed | passed | n/a |
| GF06 | GF06_assignmentRequiresKnownOrRegisteredVehicle | fleet-service | passed | passed | n/a |
| GF07 | GF07_staleSubmitIsRefusedCarNoLongerAvailable | fleet-service | passed | passed | n/a |
| GF07 | GF07_poolLoanCountsAsHolding | fleet-service | passed | passed | n/a |
| GF07 | GF07_oneOpenAssignmentPerCarConstraint | fleet-service | passed | passed | n/a |
| GF07 | GF07_staleSubmitReturnsToVehicleChoice | extra | n/a | n/a | passed |
| GF08 | GF08_assignmentReasonIsRecorded | fleet-service | passed | passed | n/a |
| GF09 | GF09_assignmentStartDateIsValidated | fleet-service | passed | passed | n/a |
| GF09 | GF09_startDateDefaultsToServerToday | extra | n/a | n/a | passed |
| GF10 | GF10_assignmentIdentifierIsUnique | fleet-service | passed | passed | n/a |
| GF11 | GF11_carRequestIsRecorded | fleet-service | passed | passed | n/a |
| GF12 | GF12_assignmentAndClaimRequireOwner | fleet-service | passed | passed | n/a |
| GF13 | GF13_currentCarIsOpenAssignment | fleet-service | passed | passed | n/a |
| GF13 | GF13_currentCarPageShowsOpenAssignment | extra | n/a | n/a | passed |
| GF14 | GF14_returnFindsOpenAssignment | fleet-service | passed | passed | n/a |
| GF14 | GF14_returnRejectsStaleAssignment | extra | passed | passed | n/a |
| GF15 | GF15_returnBeforeStartIsRejected | fleet-service | passed | passed | n/a |
| GF16 | GF16_returnReleasesCar | fleet-service | passed | passed | n/a |
| GF16 | GF16_returnNoteOverLimitIsRejected | extra | passed | passed | n/a |
| GF17 | GF17_returnOdometerHandling | fleet-service | passed | passed | n/a |
| GF18 | GF18_returnFunctionIsReachable | fleet-web | n/a | n/a | passed |
| GF19 | GF19_claimDateWithinOpenOrLookbackPeriod | fleet-service | passed | passed | n/a |
| GF19 | GF19_blankJourneyDateIsSentAsNull | extra | n/a | n/a | passed |
| GF20 | GF20_distanceWithinProfileMaximum | fleet-service | passed | passed | n/a |
| GF21 | GF21_mileageRoundsHalfUpInBothCountries | fleet-service | passed | passed | n/a |
| GF21 | GF21_mileageAmountFrozenAtSubmission | fleet-service | passed | passed | n/a |
| GF21 | GF21_mileageReimbursementMatchesHoldouts | fleet-service | passed | passed | n/a |
| GF21 | GF21_deSeedClaimsAcceptedDifference | extra | passed | passed | n/a |
| GF22 | GF22_newClaimIsPendingAndOnlyApprovedIsPaid | fleet-service | passed | passed | n/a |
| GF22 | GF22_approvalPageApprovesPendingClaim | extra | n/a | n/a | passed |
| GF23 | GF23_claimVehicleHandling | fleet-service | passed | passed | n/a |
| GF24 | GF24_claimHistoryWindow | fleet-service | passed | passed | n/a |
| GF24 | GF24_historyPageListsNewestFirst | extra | n/a | n/a | passed |
| GF25 | GF25_mileageClaimEligibility | fleet-service | passed | passed | n/a |
| GF26 | GF26_benefitPeriodLifecycle | fleet-service | passed | passed | n/a |
| GF26 | GF26_closedPeriodWithNullTotalsListsAndReturnsNoStoredInquiry | extra | passed | passed | n/a |
| GF26 | GF26_periodsCanBeOpenedAndClosed | extra | n/a | n/a | passed |
| GF27 | GF27_benefitFormulaPerProfile | fleet-service | passed | passed | n/a |
| GF27 | GF27_benefitMatchesHoldouts | fleet-service | passed | passed | n/a |
| GF27 | GF27_benefitMatchesPortalStatements | fleet-service | passed | passed | n/a |
| GF27 | GF27_inquiryShowsRunFigure | fleet-service | passed | passed | n/a |
| GF27 | GF27_failedInquiryClearsPreviousResult | extra | n/a | n/a | passed |
| GF27 | GF27_failedStatementClearsPreviousResult | extra | n/a | n/a | passed |
| GF27 | GF27_statementShowsProfileAndCalculation | extra | n/a | n/a | passed |
| GF28 | GF28_swapDayCountsForIncomingCarOnly | fleet-service | passed | passed | n/a |
| GF29 | GF29_everyHeldCarIsTaxed | fleet-service | passed | passed | n/a |
| GF30 | GF30_leaverBenefitCapAndFlag | fleet-service | passed | passed | n/a |
| GF30 | GF30_belowGradeHolderIsTaxedAndListed | extra | passed | passed | n/a |
| GF31 | GF31_periodCloseWritesOutputAndControlTotals | fleet-service | passed | passed | n/a |
| GF31 | GF31_failedRunChangesNothing | fleet-service | passed | passed | n/a |
| GF31 | GF31_closedPeriodCannotBeRerun | fleet-service | passed | passed | n/a |
| GF32 | GF32_navigationReachesEveryFunction | fleet-web | n/a | n/a | passed |
| GF32 | GF32_backSavesDraftWithoutValidation | extra | n/a | n/a | passed |
| GF32 | GF32_benefitLinkResetsView | extra | n/a | n/a | passed |
| GF32 | GF32_routeErrorClearsOnNavigation | extra | n/a | n/a | passed |
| GF33 | GF33_employeeSearch | fleet-service | passed | passed | n/a |
| GF33 | GF33_noLookupBeanFallsBackToEmptyCurrentCar | extra | passed | passed | n/a |
| GF33 | GF33_searchPageListsEmployeesWithCurrentCar | extra | n/a | n/a | passed |
| GF34 | GF34_refreshReturnsToSavedDraft | fleet-web | n/a | n/a | passed |
| GF34 | GF34_newTabResumesSameDraft | fleet-web | n/a | n/a | passed |
| GF34 | GF34_draftClearedOnSubmit | fleet-service | passed | passed | n/a |
| GF34 | GF34_draftCanBeDiscarded | fleet-service | passed | passed | n/a |
| GF34 | GF34_doubleSubmitCreatesOneRequest | fleet-service | passed | passed | n/a |
| GF34 | GF34_resumeRechecksEligibilityAndCar | fleet-service | passed | passed | n/a |

## 2. UK: 12 holdout pairs through fleet-service

`HoldoutCandidate` reads each pair's `IN` files (EMPLOYEE, VEHICLE, ASSIGNMENT, MILECLM, BENPRD). It runs every in-run employee, with all of that employee's overlapping assignments and approved in-period claims, through the uk-profile `BenefitCalculator`, as `BenefitPeriodService.close` does. It then writes `BENOUT.dat` with `BenoutWriter` and the control totals to `CONTROL.txt`.

```
cd industries/manufacturing/global-fleet/fleet-service
./mvnw -B -Puk test-compile dependency:build-classpath -Dmdep.outputFile=target/cp.txt
cd ../../../..   # repo root; check_pairs runs the candidate from here
F=industries/manufacturing/global-fleet/fleet-service
python3 industries/manufacturing/global-fleet/parity/mainframe/check_pairs.py --candidate \
  "java -cp $F/target/classes:$F/target/test-classes:$(cat $F/target/cp.txt) com.otterworks.fleet.verification.HoldoutCandidate --in {in} --out {out} --period {period}"
```

Sanity check: the reference candidate `parity/mainframe/reference/fleben01.py` gives `identical` on all 24 files (exit 0).

**`check_pairs.py --candidate` result: exit 1, failed.** 12 of 12 `BENOUT.dat` failed (differ). 12 of 12 `BENRPT.txt` failed (missing). All 12 candidate runs exited 0, and the 84 input checksums verified.

Record-level comparison of BENOUT (expected vs candidate, keyed by employee db-key, tagged with the predicates from `BenefitHoldoutTest`):

| Tag | Records | Taxable delta GBP | Mileage delta | Classification |
|---|---:|---:|---:|---|
| GF29 overlap (more than one overlapping assignment) | 198 | +115308.73 | 0.00 | expected (GF29: every held car taxed; matches the catalog's upper bound +115308.73) |
| GF29 pool loan (returned pool loan masked the open NC car) | 41 | +20985.76 | 0.00 | expected (owner-accepted, `d-poolloan-holdouts`) |
| anything else | 0 | 0.00 | 0.00 | - |

All 198 overlap records differ in vehicle, days or taxable benefit only. No record differs in miles or reimbursement, so GF21 changes nothing in the UK holdouts. The GF27 formula changes nothing: no record outside the two GF29 groups differs.

| Pair | Overlap | Pool loan | Other | Count BENRPT / candidate | Taxable BENRPT / candidate GBP | Mileage BENRPT / candidate GBP |
|---|---:|---:|---:|---|---|---|
| HP-202510 | 11 | 0 | 0 | 110 / 110 | 34005.86 / 40096.44 | 11002.41 / 11002.41 |
| HP-202511 | 13 | 0 | 0 | 109 / 109 | 32375.69 / 39958.71 | 11888.87 / 11888.87 |
| HP-202512 | 16 | 0 | 0 | 107 / 107 | 30733.66 / 40731.15 | 14061.77 / 14061.77 |
| HP-202601 | 18 | 1 | 0 | 109 / 110 | 29091.90 / 40216.60 | 12674.75 / 12674.75 |
| HP-202602 | 18 | 3 | 0 | 101 / 103 | 29136.68 / 40573.68 | 12892.28 / 12892.28 |
| HP-202603 | 16 | 5 | 0 | 105 / 108 | 28070.94 / 39799.18 | 14458.31 / 14458.31 |
| HP-202604 | 15 | 5 | 0 | 110 / 112 | 27396.44 / 39369.59 | 13634.11 / 13634.11 |
| HP-202605 | 16 | 5 | 0 | 108 / 111 | 27537.20 / 39554.82 | 16025.64 / 16025.64 |
| HP-202606 | 18 | 5 | 0 | 102 / 108 | 26925.46 / 39784.19 | 13883.34 / 13883.34 |
| HP-202607 | 20 | 5 | 0 | 106 / 109 | 25997.76 / 39795.92 | 12325.81 / 12325.81 |
| HP-202608 | 19 | 6 | 0 | 106 / 111 | 24337.02 / 38347.47 | 13972.82 / 13972.82 |
| HP-202609 | 18 | 6 | 0 | 111 / 117 | 23982.38 / 37657.73 | 15266.40 / 15266.40 |

The control totals reconcile. The 31 extra records and +136294.49 GBP taxable are exactly the two GF29 groups (115308.73 + 20985.76). Mileage is equal in every pair.

The GF27 UK inquiry figure (prorated run figure instead of the full-month rounded figure) is an expected change. No legacy screen corpus exists for the UK inquiry, so it is evidenced only by `GF27_inquiryShowsRunFigure` (passed), not by a replay.

## 3. DE: 40-case JSF corpus against the new API

Local run, no tenant. The steps:
- Started Postgres 16 in Docker and loaded `seed/jsf/001_schema.sql` and `002_seed.sql` into `legacy`.
- Booted the packaged fleet-service jar with `-Pde`; Flyway migrated the `de` schema.
- Applied `deploy/after-seed.sql` unchanged: exit 0, leaving `de.person` 215, `de.employment` 215, `de.assignment` 111, `de.car_return` 31 and `de.mileage_claim` 699 rows.
- Ran the cases once, in `requests.json` order, on that one database, as `replay.py --stage full` does. Today = recording day (2026-10-27), so no date shift was needed. The statement default period is compared by meaning, as `replay.py` masks it.

Each JSF form action was mapped to the API call the React app makes for it. I compared the API response with the recorded legacy `observed` content: messages, tables, panels and status. Seven cases render a screen with no server call in the SPA (`ui-only`).

| Context | Cases | Result |
|---|---|---|
| employees | no-query, name, id, no-match | match: 50 / 1 / 1 / 0 rows, same order, same number, name, grade and current car. The status code `T` is now `LEFT` (the after-seed maps it) |
| assignment | with-car, without-car, unknown; no-employee ui-only | match: current car IN-JD 9303 plus 2-row history; no car; 404 `EMPLOYEE_NOT_FOUND` |
| request | unknown-employee, below-grade, already-has-car, eligible, pool-no-selection, reselect, pool-select, step-three-submit, redirect; open and back ui-only | match. `already-has-car`: the eligibility endpoint answers `allowed`, but the SPA's step-1 call `PUT /car-requests/drafts/E1009106` (step `EMPLOYEE`) returns 422 `ALREADY_HAS_CAR`. `pool-no-selection`: the SPA's "Weiter" persists step `CONFIRM`, which returns 422 `VEHICLE_REQUIRED`. Submit assigns HH-VS 7629 from 2026-10-27, reason NC |
| mileage | find-unknown, find-employee, calculate, submit-invalid, submit; open ui-only | match except the expected GF21 changes: 17 km is 5.19 EUR (legacy 5.18) and 25 km is 7.63 EUR (legacy 7.62), from half-even to half-up. Km 0 returns 422 `DISTANCE_OUT_OF_RANGE` |
| statement | 2026-08, 2026-09, 2026-10-new-car, unknown, default-period; no-parameters ui-only | **3 defects**, see D2-D4 below. Unknown employee matches (404) |
| return | unknown-plate, unassigned-pool-car, found-assigned-car, date-before-start, submit; open ui-only | match. HH-VS 7629 shows `lastOdometer` 70676 from an imported legacy return |
| static | health, unmapped-404; jsf-css-resource ui-only | match (`UP`, 404) |

German message texts appear as error codes, and page-only columns (cost centre, site, list price in the panel) are not in the API. These are representation differences (JSON API vs JSF page), not rule behaviour.

GF21 check on the seed: of the 699 legacy DE claims, 172 differ from `round(km x rate, 2)` (half-up), each by exactly 0.01 EUR. That is the catalog's expected 172. The after-seed carries the frozen legacy amounts over, per GF21's frozen-at-submission rule.

## 4. Differences: classification

| # | Where | Difference | Classification |
|---|---|---|---|
| E1 | DE seed and replay (GF21) | 172 of 699 claims, EUR 0.01, half-even to half-up; replay mileage-calculate and mileage-submit +0.01 | expected |
| E2 | UK inquiry (GF27) | prorated run figure instead of the full-month rounded figure | expected (test only, no replay corpus) |
| E3 | UK holdouts (GF29) | 198 overlap employee-months, +115308.73 GBP taxable | expected; also a cutover prerequisite |
| E4 | UK holdouts (GF29) | 41 pool-loan employee-months, six employees, +20985.76 GBP | expected (owner-accepted); payroll cutover item |
| D1 | UK holdouts (GF31) | `BENRPT.txt` is not produced (12/12 missing in `check_pairs`). fleet-service keeps the control totals on the closed period instead, and they reconcile (section 2) | **defect, not on the expected list**. Route to the benefit context (or Legacy may rule that GF31 option B's stored totals replace the report) |
| D2 | DE statement 2026-08, 2026-09 (GF26/GF27) | API 404 `PERIOD_NOT_FOUND`; legacy showed the (empty) statement. `after-seed.sql` seeds `uk.benefit_period` only, so `de.benefit_period` is empty and only the current month resolves (`BenefitOpenPeriodLookup` fallback) | **defect**: after-tenant seed (platform) |
| D3 | DE statement 2026-10-new-car (GF27) | taxable 53.04 EUR vs legacy 105.55 EUR for E1009100 (HH-VS 7629, 5 days match). `commuteDistance` is 0 vs 33 km, so the 0.03 %/km commute part is missing. `after-seed.sql` does not carry `legacy.employee.commute_km` into `de.employment.commute_distance` (V50, default 0): 0 of 215 employments vs 215 of 215 legacy employees | **defect**: after-tenant seed (platform). Every DE benefit on the after tenant is understated. Red cutover data item, open item 7 |
| D4 | DE statement-default-period (GF26) | with no period, the API uses the current month (`BenefitController`, `YearMonth.now`: 202610, 53.04 EUR); legacy uses the previous month (2026-09, 0 EUR) | **defect**: benefit context |

## 5. Open items

1. **Cutover prerequisites (`d-legacy-data`)**
   - GF05 UK double-open-car holders. The catalog lists 20 UK employees holding an open NC and RP car, for fleet to confirm the actual return dates. `GF05_unconfirmedDoubleHoldersBlockCutover` passes: the cutover is blocked until they are confirmed through `/api/v1/assignments/cutover/double-holders`.
   - GF29 overlap set: the 198 UK employee-months above (30 employee db-keys in the holdouts; the catalog splits them into 194 stale NC+RP months and 4 genuine mid-month swaps). Their taxable figure is an upper bound of +115308.73 GBP until GF05 is resolved.
2. **Payroll cutover item (GF29, accepted by Legacy).** 41 UK employee-months add +20985.76 GBP taxable. Reproduced exactly here; the per-month breakdown is in [PR #2278](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2278). Payroll must be told.

   | Employee | Months | Taxable delta GBP |
   |---|---:|---:|
   | E1010720 | 8 | +8988.08 |
   | E1011231 | 9 | +6381.45 |
   | E1011434 | 8 | +3298.80 |
   | E1011364 | 2 | +1344.50 |
   | E1010608 | 7 | +672.77 |
   | E1010293 | 7 | +300.16 |

3. **DE return odometer gap (GF17).** Found on [PR #2274](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2274). Status on `8960d8319`: **closed on the after-tenant seed path by PR #2280**. `after-seed.sql` now imports the 31 legacy DE returns, with `odometer_km`, into `de.car_return`. `ReturnsService.lastOdometer` reads that table, and the replay shows HH-VS 7629 with last reading 70676. It stays listed so the production cutover load is confirmed to carry the same records.
4. **Late-approved mileage claims are never paid.** Still open. `MileageClaimService.approve` approves without checking the paid period's status. `BenefitPeriodService.close` snapshots only the claims approved at close, so a claim approved after its period closed is never paid. Devin Review found it on PR #2278: [Late approvals disappear from closed payroll](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2278#discussion_r4393264664). The fix was kept off this board (UNT16-10 canceled).
5. **No authentication or role checks.** Still open. fleet-service has no login and no permission checks. Resolve this before any exposure beyond demo tenants. Devin Review security findings on the context PRs:
   - PR #2266 (eligibility): no authz finding posted.
   - PR #2268 (assignment):
     - [Anyone can assign a car to another employee](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2268#discussion_r4392255399)
     - [Unauthorized cutover confirmations hide unresolved holders](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2268#discussion_r4392255611)
     - [Employee car history is exposed by number](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2268#discussion_r4392255767)
   - PR #2274 (returns): no authz finding posted.
   - PR #2277 (mileage):
     - [Anyone can decide mileage claims](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2277#discussion_r4392771030)
     - [Claims can be forged for other employees](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2277#discussion_r4392771460)
     - [Employee mileage and payments exposed](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2277#discussion_r4392771783)
     - [Pending claim queue exposed publicly](https://github.com/Cognition-Partner-Workshops/otterworks/pull/2277#discussion_r4392771997)
   - PR #2278 (benefit): no authz finding posted.
   - PR #2284 (shell): no authz finding posted. Its one unposted Devin Review flag is not visible on GitHub.
6. **After-tenant seed (`deploy/after-seed.sql`, `person.name`).** **Fixed by PR #2280** (`8960d8319`). It now inserts `person (employee_no, first_name, last_name)` for both de and uk. It applied cleanly to the migrated de schema in the local run above. No tenant was deployed for this report. The seed still has the separate defects D2 and D3.
7. **🔴 RED, cutover data item: German commute distance missing from the after-tenant data load.** Open; the seed is not fixed in this ticket.
   - The after-tenant load (`deploy/after-seed.sql`) does not carry `legacy.employee.commute_km` into `de.employment.commute_distance`. That column comes from V50 with default 0, so every German employee has 0 km and loses the 0.03 % per km commute part of the benefit.
   - On t-gf-after, Legacy found it on the Windows walkthrough: E1009103's October statement is 71.75 EUR on the new app and 116.95 EUR on the old portal. The car part matches exactly.
   - The difference, 45.20 EUR, is the commute part for E1009103's legacy 21 km (0.63 % against the car part's 1.00 %).
   - Locally (D3): 0 of 215 DE employments carry a commute distance, against 215 of 215 legacy employees. E1009100's October statement is 53.04 EUR against 105.55 EUR on the portal, at 33 km.
   - E1009103 holds no car in October in the local database, so that specific figure was not reproduced here.
   - Owner: the platform side (after-tenant seed). It must be fixed and DE benefit re-checked before cutover.
