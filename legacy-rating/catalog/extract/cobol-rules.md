# RATEPREM rule extraction

Scope: phase 1, COBOL batch only, extracted from `demo-insrules` at `3d1c5662441923c6361912e088f2f9c60ae6d6e9`. After the [shared-table cross-check](cobol-crosscheck.md): **48 total, 29 proven, 12 from-table, 3 amber, 4 unproven**.

`make insrules-reset` executed all 200 committed `fixtures/policies.dat` records: `RATEPREM READ=0000200 OK=0000190 DEC=0000007 REJ=0000003` and `QUOTE READ=200 OK=190 DEC=7 REJ=3`. Evidence below comes from `build/cobol.dat`, decoded using `cobol/copybooks/RATEOUT.cpy`, and the corresponding output from `build/pharo.txt`. Dollar values are decoded from cents. `proven` means the relevant outcome is visible in both outputs; `from-table` means the executed result demonstrates a rule derived from a specific table row. `amber` preserves observed disagreements rather than inferring a quote-side cause. Smalltalk method citations and the full shared-table cross-check belong to the parent catalog.

## 0130-OPEN-END-DATE

| ID | Rule | Citation | Executed evidence | Status |
| --- | --- | --- | --- | --- |
| R-COB-01 | A blank end date on a class, territory, or override row leaves it in force from its start date. | `RATEPREM.cbl:0130-OPEN-END-DATE` 223–229; callers 110–138, 172–186; `tables/class-factors.dat:3`, `tables/territory-factors.dat:4`, `tables/overrides.dat:4` | P0000015: rate 4.1500 and factor 0.950 after January 1; P0000035 and P0000091: factor 1.600, source O on March 1 and December 22. | proven |

## 1000-RATE-POLICY

| ID | Rule | Citation | Executed evidence | Status |
| --- | --- | --- | --- | --- |
| R-COB-02 | A policy that fails a validation or lookup or is declined by eligibility does not proceed to premium or fee calculation. | `RATEPREM.cbl:1000-RATE-POLICY` 231–262 | P0000013 (REJ/LN), P0000043 (REJ/EX) and P0000040 (DEC/EX04): zero base, modified premium and total. | proven |

## 1100-VALIDATE-LINE

| ID | Rule | Citation | Executed evidence | Status |
| --- | --- | --- | --- | --- |
| R-COB-03 | GL, PR and CA pass line validation and proceed to exposure validation. | `RATEPREM.cbl:1100-VALIDATE-LINE` 276–281; dispatch 239–242 | P0000001 (GL), P0000006 (PR), P0000010 (CA): OK. | proven |
| R-COB-04 | Every other line is rejected with reason LN. | `RATEPREM.cbl:1100-VALIDATE-LINE` 276–281 | P0000013 (WC): REJ/LN even though a WC class exists in `tables/class-factors.dat:16`. | proven |

## 1200-VALIDATE-EXPOSURE

| ID | Rule | Citation | Executed evidence | Status |
| --- | --- | --- | --- | --- |
| R-COB-05 | Once the line is accepted, exposure at or below zero is rejected with reason EX. | `RATEPREM.cbl:1200-VALIDATE-EXPOSURE` 283–287 | P0000043 (negative) and P0000044 (zero): REJ/EX. | proven |

## 2000-CHECK-ELIGIBILITY

| ID | Rule | Citation | Executed evidence | Status |
| --- | --- | --- | --- | --- |
| R-COB-06 | Eligibility uses the first row matching the policy's line, class and exact state when one exists. | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY` 291–304; `tables/line-eligibility.dat:5` | P0000040 (CA/7219/NY): DEC/EX04; P0000041 (same line/class, IL): OK. | proven |
| R-COB-07 | If there is no exact state row, eligibility uses the first all-state row for the same line and class. | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY` 302–310; `tables/line-eligibility.dat:3–4,6` | P0000005 (GL/91111/IL): DEC/EX01; P0000009 (PR/0567/IL): DEC/EX02; P0000042 (CA/7911/NY): OK. | proven |
| R-COB-08 | If neither an exact state nor an all-state eligibility row matches, the policy continues to the class lookup. | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY` 291–310; dispatch 246–248; `tables/line-eligibility.dat:5` (NY-only) | P0000041 (CA/7219/IL): OK and rate 1450.0000 despite the NY-only decline row. | proven |

## 2010-APPLY-ELIGIBILITY

| ID | Rule | Citation | Executed evidence | Status |
| --- | --- | --- | --- | --- |
| R-COB-09 | An eligibility row marked N declines the policy with that row's reason. | `RATEPREM.cbl:2010-APPLY-ELIGIBILITY` 312–316; `tables/line-eligibility.dat:3–5` | P0000005: DEC/EX01; P0000009: DEC/EX02; P0000040: DEC/EX04. | from-table |
| R-COB-10 | An eligibility row not marked N does not decline the policy. | `RATEPREM.cbl:2010-APPLY-ELIGIBILITY` 312–316; `tables/line-eligibility.dat:6` | P0000042 (Y row): OK, base $1,560.00. | from-table |

## 2100-LOOKUP-CLASS

| ID | Rule | Citation | Executed evidence | Status |
| --- | --- | --- | --- | --- |
| R-COB-11 | The base rate comes from the first row matching both line and class whose effective dates include the policy date. | `RATEPREM.cbl:2100-LOOKUP-CLASS` 318–335; `tables/class-factors.dat:3,5–6` | P0000001: rate 4.1500, base $871.50; P0000028 and P0000030 straddle the dated class change. | proven |
| R-COB-12 | If no class row matching the line and class is in force, the policy is rejected with reason CL. | `RATEPREM.cbl:2100-LOOKUP-CLASS` 318–332; `tables/class-factors.dat:5–6` (example dated keys) | No fixture reaches this: the policies that pass eligibility have an in-force class row. | unproven |
| R-COB-13 | GL class 41650 has a base rate of 2.1000 for January 1 through June 30, 2026. | `RATEPREM.cbl:2100-LOOKUP-CLASS` 318–335; `tables/class-factors.dat:5` | P0000028 on June 30: rate 2.1000, base $798.00. | from-table |
| R-COB-14 | GL class 41650 has a base rate of 2.2500 from July 1, 2026 onward. | `RATEPREM.cbl:2100-LOOKUP-CLASS` 318–335; `tables/class-factors.dat:6` | P0000030 on July 1: rate 2.2500, base $855.00. | from-table |

## 2200-LOOKUP-TERRITORY

| ID | Rule | Citation | Executed evidence | Status |
| --- | --- | --- | --- | --- |
| R-COB-15 | The first in-force row matching both line and territory supplies the territory factor with source T, even when the policy explicitly requests territory 000. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY` 338–350; `tables/territory-factors.dat:3–4,9` | P0000014: 000 gives 1.000/T; P0000015 and P0000020: territory 010 gives 0.950/T in GL and 0.900/T in PR. | proven |
| R-COB-16 | If the requested territory has no in-force row for the line, the first in-force territory 000 row for that line supplies the factor with source D. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY` 338–361; `tables/territory-factors.dat:3,8,12` | P0000018 (unknown GL/099) and P0000023 (expired PR/060): 1.000/D. | proven |
| R-COB-17 | If neither the requested territory nor territory 000 has an in-force row for the line, the policy is rejected with reason TR. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY` 338–365; `tables/territory-factors.dat:3,8,13` (defaults) | No fixture reaches this: the shipped defaults are in force over the fixture dates for all accepted lines. | unproven |
| R-COB-18 | GL territory 040 supplies factor 1.200 from January 1 through June 30, 2026, before any override. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY` 338–350; `tables/territory-factors.dat:6` | P0000027 on June 30: 1.200/T, base $1,494.00. | from-table |
| R-COB-19 | GL territory 040 supplies factor 1.350 from July 1, 2026 onward, before any override. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY` 338–350; `tables/territory-factors.dat:7` | P0000029 on July 1: 1.350/T, base $1,680.75. | from-table |

## 2300-LOOKUP-OVERRIDE

| ID | Rule | Citation | Executed evidence | Status |
| --- | --- | --- | --- | --- |
| R-COB-20 | The first override in force for the policy's line, class and original territory replaces, rather than multiplies, the territory factor and sets source O. | `RATEPREM.cbl:2300-LOOKUP-OVERRIDE` 368–382; `tables/overrides.dat:3`, `tables/territory-factors.dat:6` | P0000031: 1.500/O instead of the 1.200 territory factor or a stacked 1.800; base $1,399.65. | proven |
| R-COB-21 | If no override matches all keys and dates, the previously selected territory factor and its source remain unchanged. | `RATEPREM.cbl:2300-LOOKUP-OVERRIDE` 368–382; `tables/overrides.dat:3–5`, `tables/territory-factors.dat:3,5,10,14` | P0000033 (wrong territory): 1.100/T; P0000034 (before start): 1.250/T; P0000038 (after end): 1.300/T; P0000018 keeps 1.000/D. | proven |
| R-COB-22 | GL class 91580 in territory 040 gets factor 1.500 from January 1 through December 31, 2026. | `RATEPREM.cbl:2300-LOOKUP-OVERRIDE` 368–382; `tables/overrides.dat:3` | P0000031 and P0000032 (the latter on December 31): 1.500/O. | from-table |
| R-COB-23 | PR class 0702 in territory 030 gets factor 1.600 from March 1, 2026 onward. | `RATEPREM.cbl:2300-LOOKUP-OVERRIDE` 368–382; `tables/overrides.dat:4` | P0000035 on March 1: 1.600/O; P0000034 on February 28: 1.250/T. | from-table |
| R-COB-24 | CA class 7219 in territory 020 gets factor 1.550 from January 1 through September 30, 2026, if it passes eligibility. | `RATEPREM.cbl:2300-LOOKUP-OVERRIDE` 368–382; `tables/overrides.dat:5` | P0000037 on September 30: 1.550/O; P0000038 on October 1: 1.300/T. | from-table |

## 3000-BASE-PREMIUM

| ID | Rule | Citation | Executed evidence | Status |
| --- | --- | --- | --- | --- |
| R-COB-25 | Base premium is exposure times the class rate rounded to cents, then times the selected territory factor and rounded to cents again. | `RATEPREM.cbl:3000-BASE-PREMIUM` 384–387 | P0000092: 754.14 × 0.5200 rounds to $392.15, then × 1.150 gives $450.97 in both outputs; rounding only once would give $450.98. | proven |

## 3100-EXPERIENCE-MOD

| ID | Rule | Citation | Executed evidence | Status |
| --- | --- | --- | --- | --- |
| R-COB-26 | Three or more claims in the last three years increase premium by 25%. | `RATEPREM.cbl:3100-EXPERIENCE-MOD` 389–398 | P0000047 (3 claims): $867.35 → $1,084.19. | proven |
| R-COB-27 | No claims in the last three years and at least three years in business reduce premium by 10%. | `RATEPREM.cbl:3100-EXPERIENCE-MOD` 389–398 | P0000045 (0 claims, 3 years): $867.35 → $780.62. | proven |
| R-COB-28 | If neither experience condition is met, experience leaves premium unchanged. | `RATEPREM.cbl:3100-EXPERIENCE-MOD` 389–398 | P0000046 (0 claims, 2 years): $867.35 → $867.35; P0000001 (1 claim): $871.50 → $871.50. | proven |

## 3200-DEDUCTIBLE-CREDIT

| ID | Rule | Citation | Executed evidence | Status |
| --- | --- | --- | --- | --- |
| R-COB-29 | PR or CA with a deductible of at least $5,000 gets an 8% credit. | `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT` 401–413 | P0000051 (PR): $575.10 → $529.09; P0000052 (CA): $1,555.50 → $1,431.06. | proven |
| R-COB-30 | PR or CA with a deductible of $2,500 to less than $5,000 gets a 5% credit. | `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT` 401–413 | P0000050 ($2,500): $575.10 → $546.35. | proven |
| R-COB-31 | PR or CA with a deductible of $1,000 to less than $2,500 gets a 2% credit. | `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT` 401–413 | P0000049 ($1,000): $575.10 → $563.60. | proven |
| R-COB-32 | PR or CA with a deductible below $1,000 gets no deductible credit. | `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT` 401–413 | P0000048 ($999): $575.10 → $575.10. | proven |
| R-COB-33 | A line other than PR or CA gets no deductible credit. | `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT` 401–413 | P0000053 (GL, $5,000 deductible): $726.00 → $726.00. | proven |

## 3300-SCHEDULE-MOD

| ID | Rule | Citation | Executed evidence | Status |
| --- | --- | --- | --- | --- |
| R-COB-34 | A requested schedule credit greater than 25% is limited to a 25% credit. | `RATEPREM.cbl:3300-SCHEDULE-MOD` 415–423 | P0000054 (−30%): $730.40 → $547.80. | proven |
| R-COB-35 | A requested schedule debit greater than 25% is limited to a 25% debit. | `RATEPREM.cbl:3300-SCHEDULE-MOD` 415–423 | P0000057 (+40%): $730.40 → $913.00. | proven |
| R-COB-36 | A schedule adjustment in the −25% to +25% range applies as requested. | `RATEPREM.cbl:3300-SCHEDULE-MOD` 415–423 | P0000055 (−25%): $730.40 → $547.80; P0000056 (+15%): $730.40 → $839.96. | proven |

## 3400-MULTI-POLICY

| ID | Rule | Citation | Executed evidence | Status |
| --- | --- | --- | --- | --- |
| R-COB-37 | GL or PR with the multi-policy flag set to Y gets a 5% credit. | `RATEPREM.cbl:3400-MULTI-POLICY` 425–429 | P0000058 (GL): $880.00 → $836.00; P0000059 (PR): $760.00 → $722.00. | proven |
| R-COB-38 | No multi-policy credit applies when the flag is not Y or the line is not GL or PR. | `RATEPREM.cbl:3400-MULTI-POLICY` 425–429 | P0000001 (GL, N): $871.50 → $871.50; P0000060 (CA, Y): $1,560.00 → $1,560.00. | proven |

## 3450-WIND-SURCHARGE

| ID | Rule | Citation | Executed evidence | Status |
| --- | --- | --- | --- | --- |
| R-COB-39 | Florida PR uses the last PR/WND territory row as a separate wind multiplier regardless of its effective dates. | `RATEPREM.cbl:3450-WIND-SURCHARGE` 431–443; `tables/territory-factors.dat` (no PR/WND row) | No fixture reaches this: Florida PR is present but the required row is absent. | unproven |
| R-COB-40 | Florida PR with no PR/WND row keeps the wind multiplier at 1.000. | `RATEPREM.cbl:3450-WIND-SURCHARGE` 433–443; `tables/territory-factors.dat:8–12` (PR rows, none WND) | P0000101 (PR/FL): base $4,306.52, modified $5,383.15 from the 25% experience debit alone; no minimum or other premium modifier changes it. | proven |

## 3500-MINIMUM-PREMIUM

| ID | Rule | Citation | Executed evidence | Status |
| --- | --- | --- | --- | --- |
| R-COB-41 | The first minimum row matching the policy's line and state wins over the all-state minimum for the same line. | `RATEPREM.cbl:3500-MINIMUM-PREMIUM` 446–464; `tables/minimum-premium.dat:3–4,6–7` | P0000061 (GL/CA): $750.00 rather than $500.00; P0000063 (CA/TX): $1,200.00 rather than $1,000.00. | from-table |
| R-COB-42 | If no exact state minimum matches, the first all-state minimum for the same line is used. | `RATEPREM.cbl:3500-MINIMUM-PREMIUM` 446–464; `tables/minimum-premium.dat:3,5–6` | P0000062 (GL/IL): $500.00; P0000070 (PR/IL): $350.00; P0000082 (CA/CA) selects the CA wildcard as shown below. | from-table |
| R-COB-43 | With no CA/CA minimum row, a California commercial-auto policy uses the CA all-state minimum of $1,000.00. | `RATEPREM.cbl:3500-MINIMUM-PREMIUM` 446–468; `InsQuoteEngine>>applyMinimum:premium:quote:` (`InsQuoteEngine.class.st` 147–157); `tables/minimum-premium.dat:6` | P0000082: both select $1,000.00 and flag Y; COBOL floors after the +25% schedule factor and emits $1,000.00, while Pharo floors before that factor and emits $1,250.00. See R-COB-44/45 for the ordering difference. | from-table |
| R-COB-44 | If premium after all credits and debits is below the selected minimum, the batch raises it to that minimum and sets the minimum flag to Y. | `RATEPREM.cbl:1000-RATE-POLICY` 252–261; `RATEPREM.cbl:3500-MINIMUM-PREMIUM` 465–469; `tables/minimum-premium.dat:3–5` | P0000065: COBOL $500.00/Y vs Pharo $401.07/N; P0000066: $350.00/Y vs $282.63/Y; P0000200: $750.00/Y vs $675.00/Y. The placement of the batch floor is explicit; the quote path does not produce that floor in these cases. | amber |
| R-COB-45 | If premium after all credits and debits meets or exceeds the selected minimum, the batch leaves it unchanged and keeps the minimum flag at N. | `RATEPREM.cbl:3500-MINIMUM-PREMIUM` 465–469; initialization 238; `tables/minimum-premium.dat:3` | P0000001 agrees at $871.50/N; P0000067 crosses above the floor after a debit and differs: COBOL $554.40/N vs Pharo $600.00/Y. | amber |
| R-COB-46 | If neither a specific state nor an all-state minimum matches, the premium is not raised and the minimum flag remains N. | `RATEPREM.cbl:3500-MINIMUM-PREMIUM` 446–469; initialization 238; `tables/minimum-premium.dat:3,5–6` (shipped defaults) | No fixture reaches this: every line that reaches this paragraph has an all-state minimum. | unproven |

## 3600-POLICY-FEE

| ID | Rule | Citation | Executed evidence | Status |
| --- | --- | --- | --- | --- |
| R-COB-47 | Every rated policy adds a $35.00 fee to its modified premium. | `RATEPREM.cbl:3600-POLICY-FEE` 471–473; fee constant 75 | P0000015: modified $709.65, COBOL fee $35.00 and total $744.65 in both outputs. | proven |
| R-COB-48 | The batch total is modified premium plus the policy fee only; it does not charge for additional insureds or endorsements. | `RATEPREM.cbl:1000-RATE-POLICY` 252–262; `RATEPREM.cbl:3600-POLICY-FEE` 471–473; `cobol/copybooks/POLREC.cpy:16–19` | P0000068 and P0000069: COBOL total $1,280.00 for both with different additional-insured and endorsement inputs; Pharo totals $1,405.00 and $1,550.00 with corresponding nonzero endorsement amounts. | amber |

## Observations for the shared-table cross-check

- **Exclusivity:** Exact territory and fallback cannot both be selected (P0000014 vs P0000018); the override replaces the selected factor without stacking (P0000031 replaces T; no fixture reaches a D-to-O replacement). The two dated GL/41650 class rows and GL/040 territory rows are mutually exclusive at June 30 / July 1 (P0000028 / P0000030 and P0000027 / P0000029). Experience and deductible tiers are first-match branches (P0000045–P0000047 and P0000048–P0000051).
- **Fallback:** P0000018 distinguishes missing territory from exact 000 in P0000014, and P0000023 shows that an expired exact row also triggers fallback. P0000041 defaults to eligible; P0000062 shows wildcard minimum selection. No fixture reaches CL, TR or missing-minimum fallback.
- **Paired keys:** Class pairs line and class plus effective date; territory pairs line and territory plus effective date (same territory, different factors in P0000015 / P0000020). Eligibility pairs line and class plus exact or wildcard state (P0000040 / P0000041); the source gives the exact row priority, but no fixture reaches an exact/wildcard collision for the same eligibility pair. Minimum pairs line and state (P0000061 / P0000062). Override pairs class with the policy's original territory within a line and date range (P0000031 / P0000033 for the territory, P0000027 / P0000031 for the class).
- **Rows not selected:** No fixture reaches `tables/class-factors.dat:8,12` for rating because the matching classes decline first (P0000005 / P0000009). No fixture reaches WC class (`tables/class-factors.dat:16`) or WC minimum (`tables/minimum-premium.dat:8`) because WC is rejected at line validation (P0000013). No fixture selects expired `tables/territory-factors.dat:12`; P0000023 reaches the lookup but falls back. There is no PR/WND row; P0000101 demonstrates the neutral multiplier.
