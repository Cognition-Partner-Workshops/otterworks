# Pharo quote screen — phase 1 extraction

Baseline: `demo-insrules` at [3d1c566](https://github.com/Cognition-Partner-Workshops/otterworks/commit/3d1c5662441923c6361912e088f2f9c60ae6d6e9). The [screen delegates to the quote engine](../smalltalk/src/InsRating/InsQuoteScreen.class.st#L28-L34); [the fixture runner calls the same engine](../smalltalk/src/InsRating/InsQuoteBatch.class.st#L13-L24). Form parsing and rendering are not rating rules and the headless run does not exercise them.

`make insrules-reset` executed all 200 baseline policies in Pharo and COBOL: each emitted 190 OK, 7 DEC and 3 REJ. Evidence below is from `build/pharo.txt` and `build/cobol.dat`, joined by ID from [the original fixture](../fixtures/policies.dat). The reset script also invokes the comparison target and tolerates its nonzero exit; no modern parity work was done for this extraction. Money in evidence columns is in cents; exact rate and factor are recorded in COBOL output, and evidenced in Pharo by the base premium and factor-source output. Unprinted intermediate values are arithmetic reconstructions, not runtime trace fields.

Each heading is the primary Smalltalk source citation for its rules. A COBOL paragraph in a heading applies to all its rules unless an entry says otherwise. Table references are file line numbers under `legacy-rating/tables/`; a rule without a table reference is not table-driven. The [Ask Devin / DeepWiki search](https://partner-workshops.devinenterprise.com/search/api_4b8d3eac-b121-4be8-b34c-495c2b261971) could not source the requested branch, so the citations below come from the checked-out source, not wiki inference.

Extraction subtotal (before cross-stack deduplication): **65 found**, of which **31 proven**, **16 from-table** (also execution-backed), **10 amber**, and **8 unproven**.

## [`InsQuoteEngine>>quote:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L28-L40)
COBOL: [`RATEPREM.cbl:1000-RATE-POLICY`, 231–262](../cobol/RATEPREM.cbl#L231-L262).

| ID | Statement | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- |
| R-ST-01 | Once a validation or lookup rejects or declines a policy, rating stops and no premium or fee is charged. | `P0000013` and `P0000040`: respectively REJ/LN and DEC/EX04, with no base, fee or total in either stack (all zero). | proven |

## [`InsQuoteEngine>>validateLine:into:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L59-L61) and [`validateExposure:into:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L64-L66)

| ID | Statement | Citation | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- | --- |
| R-ST-02 | Reject a line other than GL, PR or CA with LN. | `RATEPREM.cbl:1100-VALIDATE-LINE`, 276–281. | `P0000013`: WC is REJ/LN in both despite WC class and minimum table records. | proven |
| R-ST-03 | Reject exposure of zero or less with EX. | `RATEPREM.cbl:1200-VALIDATE-EXPOSURE`, 283–287. | `P0000043` (negative) and `P0000044` (zero): both stacks REJ/EX. | proven |

## [`InsQuoteEngine>>checkEligibility:into:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L69-L77)
COBOL: [`RATEPREM.cbl:2000-CHECK-ELIGIBILITY` and `2010-APPLY-ELIGIBILITY`, 291–316](../cobol/RATEPREM.cbl#L291-L316).

| ID | Statement | Table citation | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- | --- |
| R-ST-04 | Decline GL class 91111 in all states with EX01. | `tables/line-eligibility.dat:3` | `P0000005`: DEC/EX01 in both. | from-table |
| R-ST-05 | Decline PR class 0567 in all states with EX02. | `tables/line-eligibility.dat:4` | `P0000009`: DEC/EX02 in both. | from-table |
| R-ST-06 | Decline CA class 7219 in NY with EX04. | `tables/line-eligibility.dat:5` | `P0000040` (NY): DEC/EX04; `P0000041` otherwise identical in IL: OK in both. | from-table |
| R-ST-07 | Treat CA class 7911 as eligible in all states. | `tables/line-eligibility.dat:6` | `P0000042` (NY), `P0000012` (IL): OK in both. | from-table |
| R-ST-08 | When no exact-state row matches the line and class, use the matching all-states row. | `tables/line-eligibility.dat:3–4,6` | `P0000005`: GL/91111/IL gets wildcard EX01; `P0000009`: PR/0567/IL gets wildcard EX02 in both. | proven |
| R-ST-09 | When neither the exact-state nor all-states row matches the line and class, do not decline for eligibility. | `tables/line-eligibility.dat:5` | `P0000041` is OK in both; only NY has a row for its CA/7219 pair. | proven |
| R-ST-10 | Prefer the exact-state row when both exact and all-states rows match the same line and class. | `tables/line-eligibility.dat:3–6` | No fixture reaches this: no pair has both rows. | unproven |

## [`InsQuoteEngine>>lookupClassRate:into:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L80-L87)
COBOL: [`RATEPREM.cbl:2100-LOOKUP-CLASS`, 318–335](../cobol/RATEPREM.cbl#L318-L335).

| ID | Statement | Table citation | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- | --- |
| R-ST-11 | Take the base rate from the first in-force row matching both the policy line and class. | `tables/class-factors.dat:3,9` | `P0000001` (GL/91340) and `P0000006` (PR/0311) select 4.1500 and 0.3800 respectively from the paired keys; bases 87150 and 57000 in both. No fixture isolates ordering between duplicate in-force rows: there are none. | proven |
| R-ST-12 | Use a GL/41650 rate of 2.1000 for effective dates from January 1 through June 30, 2026. | `tables/class-factors.dat:5` | `P0000028` on June 30: base 79800 at factor 0.950 in both. | from-table |
| R-ST-13 | Use a GL/41650 rate of 2.2500 from July 1, 2026 onward. | `tables/class-factors.dat:6` | `P0000030` on July 1: base 85500 at factor 0.950 in both. | from-table |
| R-ST-14 | Reject with CL when there is no in-force row for the policy's line and class. | `tables/class-factors.dat:3–16` (searched) | No fixture reaches this; all 190 policies reaching class lookup match. | unproven |

## [`InsQuoteEngine>>lookupTerritory:into:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L90-L104)
COBOL: [`RATEPREM.cbl:2200-LOOKUP-TERRITORY`, 338–365](../cobol/RATEPREM.cbl#L338-L365).

| ID | Statement | Table citation | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- | --- |
| R-ST-15 | An in-force row for the policy's line and requested territory supplies its territory factor and marks the source T. | `tables/territory-factors.dat:3,6,11` | `P0000017` (GL/040) gets 1.200/T and `P0000022` (PR/040) gets 1.150/T; `P0000001` explicitly requests 000 and still gets T. | proven |
| R-ST-16 | Use a GL/040 factor of 1.200 for effective dates from January 1 through June 30, 2026. | `tables/territory-factors.dat:6` | `P0000027` on June 30: source T, base 149400 in both. | from-table |
| R-ST-17 | Use a GL/040 factor of 1.350 from July 1, 2026 onward. | `tables/territory-factors.dat:7` | `P0000029` on July 1: source T, base 168075 in both. | from-table |
| R-ST-18 | If the requested territory has no in-force row, use that line's in-force 000 row and mark the source D. | `tables/territory-factors.dat:3,8,12` | `P0000018` (missing 099) gets 1.000/D, base 74700; `P0000023` (expired PR/060) gets 1.000/D, base 45600 in both. | proven |
| R-ST-19 | If neither the requested territory nor the 000 fallback is in force for the line, reject with TR. | `tables/territory-factors.dat:3,8,13` (fallback rows) | No fixture reaches this; every policy reaching territory lookup finds a direct or fallback row. | unproven |

## [`InsQuoteEngine>>lookupOverride:into:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L107-L117)
COBOL: [`RATEPREM.cbl:2300-LOOKUP-OVERRIDE`, 368–382](../cobol/RATEPREM.cbl#L368-L382).

| ID | Statement | Table citation | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- | --- |
| R-ST-20 | Use override factor 1.500 for GL/91580/040 effective January 1 through December 31, 2026. | `tables/overrides.dat:3` | `P0000031`, `P0000032` (last day): O, base 139965 in both. | from-table |
| R-ST-21 | Use override factor 1.600 for PR/0702/030 effective March 1, 2026 onward. | `tables/overrides.dat:4` | `P0000035` (first day): O, base 341120 in both. | from-table |
| R-ST-22 | Use override factor 1.550 for CA/7219/020 effective January 1 through September 30, 2026. | `tables/overrides.dat:5` | `P0000037` (last day): O, base 899000 in both. | from-table |
| R-ST-23 | The first in-force override for the exact line, class and requested territory replaces the prior factor without multiplying it and marks the source O. | `tables/overrides.dat:3–5`; `tables/territory-factors.dat:6–7,10,14` | `P0000031` and `P0000032`: different underlying territory factors but the same O and base 139965 in both. No fixture reaches competing overrides; the table has no duplicates. | proven |
| R-ST-24 | When no in-force override matches all keys, retain the selected territory factor and its original source. | `tables/overrides.dat:3–5`; `tables/territory-factors.dat:3,5–6,10,14` | `P0000017` (wrong class), `P0000033` (wrong territory), `P0000034` (before start), `P0000038` (after end) retain T; `P0000018` retains D in both. | proven |

## [`InsRatingTables>>row:from:inForceOn:`](../smalltalk/src/InsRating/InsRatingTables.class.st#L46-L53)
COBOL: [`RATEPREM.cbl:0130-OPEN-END-DATE`, 224–229](../cobol/RATEPREM.cbl#L224-L229), `2100-LOOKUP-CLASS`, 322–325; `2200-LOOKUP-TERRITORY`, 342–356; `2300-LOOKUP-OVERRIDE`, 372–376.

| ID | Statement | Table citation | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- | --- |
| R-ST-25 | A row is in force on both its start date and its stated end date. | `tables/overrides.dat:4–5` | `P0000034`/ `P0000035` switch T to O at the start; `P0000037`/ `P0000038` switch O to T only after the end, in both. | proven |
| R-ST-26 | A blank end date leaves the row in force from its start without an expiry. | `tables/class-factors.dat:6`; `tables/territory-factors.dat:3` | `P0000128` effective September 28 still uses both open-ended rows, base 286979/T in both. | proven |

## [`InsQuoteEngine>>basePremium:quote:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L120-L124) and [`round:scale:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L22-L25)
COBOL: [`RATEPREM.cbl:3000-BASE-PREMIUM`, 384–387](../cobol/RATEPREM.cbl#L384-L387).

| ID | Statement | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- |
| R-ST-27 | Multiply exposure by the base rate and round half up to the cent before applying the territory factor. | `P0000120`: exposure times rate yields 577516.5 cents, factor 1.000, base 577517 in both. `P0000092`: both give 45097; rounding only after both multiplications would give 45098. | proven |
| R-ST-28 | Multiply the rounded amount by the selected territory factor and round half up to the cent for base premium. | `P0000065`: 55550 × 0.950 = 52772.5 cents, base 52773 in both. | proven |

## [`InsQuoteEngine>>experienceMod:premium:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L127-L133)
COBOL: [`RATEPREM.cbl:3100-EXPERIENCE-MOD`, 389–398](../cobol/RATEPREM.cbl#L389-L398).

| ID | Statement | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- |
| R-ST-29 | Increase premium by 25% for three or more claims in the last three years. | `P0000047`: 3 claims, base 86735 to modified 108419 in both. | proven |
| R-ST-30 | Reduce premium by 10% for zero claims and at least three years in business. | `P0000045`: 0 claims, 3 years, base 86735 to modified 78062 in both. | proven |
| R-ST-31 | Otherwise leave the premium unchanged by experience. | `P0000046`: 0 claims, 2 years, base and modified 86735; `P0000001`: 1 claim, 5 years, base and modified 87150 in both. | proven |

## [`InsQuoteEngine>>deductibleCredit:premium:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L136-L144)
COBOL: [`RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT`, 401–413](../cobol/RATEPREM.cbl#L401-L413).

| ID | Statement | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- |
| R-ST-32 | GL receives no deductible credit. | `P0000053`: GL, $5,000 deductible, base and modified 72600 in both. | proven |
| R-ST-33 | For PR or CA, a deductible of at least $5,000 earns an 8% credit. | `P0000051` PR: 57510 to 52909; `P0000052` CA: 155550 to 143106 in both. | proven |
| R-ST-34 | For PR or CA, a deductible from $2,500 up to but not including $5,000 earns a 5% credit. | `P0000050`: $2,500, base 57510 to modified 54635 in both. | proven |
| R-ST-35 | For PR or CA, a deductible from $1,000 up to but not including $2,500 earns a 2% credit. | `P0000049`: $1,000, base 57510 to modified 56360 in both. | proven |
| R-ST-36 | For PR or CA, a deductible below $1,000 earns no credit. | `P0000048`: $999, base and modified 57510 in both. | proven |

## [`InsQuoteEngine>>applyMinimum:premium:quote:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L147-L157)
COBOL: [`RATEPREM.cbl:3500-MINIMUM-PREMIUM`, 446–469](../cobol/RATEPREM.cbl#L446-L469).

| ID | Statement | Table citation | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- | --- |
| R-ST-37 | Apply a $750 minimum in California for GL rather than the GL all-states minimum. | `tables/minimum-premium.dat:3–4` | `P0000061` (CA) and `P0000062` (IL) both start at 44000; both stacks floor to 75000 and 50000 respectively. | from-table |
| R-ST-38 | Apply a $1,200 minimum in Texas for CA rather than the CA all-states minimum. | `tables/minimum-premium.dat:6–7` | `P0000026`: 103700 to 120000 with minimum Y in both, above the 100000 wildcard. | from-table |
| R-ST-39 | When there is no state-specific minimum for GL use $500. | `tables/minimum-premium.dat:3` | `P0000062`: 44000 to 50000 with minimum Y in both. | from-table |
| R-ST-40 | When there is no state-specific minimum for PR use $350. | `tables/minimum-premium.dat:5` | `P0000064`: 27360 to 35000 with minimum Y in both. | from-table |
| R-ST-41 | When there is no state-specific minimum for CA use $1,000. | `tables/minimum-premium.dat:6` | `P0000121` (CA policy in California): 88400 base; both report 100000 modified with minimum Y. | from-table |
| R-ST-42 | If neither a state-specific nor all-states minimum matches the policy line, impose no minimum. | `tables/minimum-premium.dat:3–8` (searched) | No fixture reaches this: each permitted line has an all-states row. | unproven |
| R-ST-43 | Raise premium to the selected minimum and mark it applied only when the current premium is lower. | `tables/minimum-premium.dat:3` | `P0000062`: 44000 to 50000/Y; `P0000001`: 87150 unchanged/N, in both. No fixture reaches exact equality. | proven |

## [`InsQuoteEngine>>rate:into:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L43-L56)
COBOL: [`RATEPREM.cbl:1000-RATE-POLICY`, 252–262](../cobol/RATEPREM.cbl#L252-L262), `3500-MINIMUM-PREMIUM`, 446–469 and `3600-POLICY-FEE`, 471–473.

| ID | Statement | Table citation | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- | --- |
| R-ST-44 | After experience and deductible adjustments, the screen applies the minimum before schedule and multi-policy adjustments. | `tables/minimum-premium.dat:3–6` | `P0000066`: Pharo floors at 35000 then discounts to 28263/Y, COBOL discounts then floors to 35000/Y; `P0000065`: Pharo 40107/N vs COBOL 50000/Y; `P0000067`: 60000/Y vs 55440/N; `P0000082`: 125000/Y vs 100000/Y; `P0000200`: 67500/Y vs 75000/Y. | amber: batch puts the floor last |
| R-ST-45 | The screen's total includes modified premium, endorsements and the policy fee. | No table used. | `P0000071`: Pharo 416000 + 12500 + 3500 = 432000; COBOL total 419500 excludes endorsements. | amber: batch totals do not include endorsements |

## [`InsQuoteEngine>>scheduleMod:premium:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L160-L164)
COBOL: [`RATEPREM.cbl:3300-SCHEDULE-MOD`, 415–423](../cobol/RATEPREM.cbl#L415-L423).

| ID | Statement | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- |
| R-ST-46 | A schedule adjustment below −25% is applied as −25%. | `P0000054` (−30%) and `P0000055` (−25%): identical base 73040 and modified 54780 in both. | proven |
| R-ST-47 | A schedule adjustment above +25% is applied as +25%. | `P0000057` (+40%): 73040 to 91300 in both. | proven |
| R-ST-48 | A schedule adjustment between −25% and +25% inclusive applies as entered, with zero leaving the premium unchanged. | `P0000056` (+15%): 73040 to 83996; `P0000080` (−20%): 155139 to 124111; `P0000001` (0): unchanged in both. | proven |

## [`InsQuoteEngine>>multiPolicy:premium:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L167-L170)
COBOL: [`RATEPREM.cbl:3400-MULTI-POLICY`, 425–429](../cobol/RATEPREM.cbl#L425-L429).

| ID | Statement | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- |
| R-ST-49 | A selected multi-policy discount reduces the premium by 5% on GL or PR. | `P0000058` (GL): 88000 to 83600; `P0000059` (PR): 76000 to 72200 in both. | proven |
| R-ST-50 | CA does not receive a multi-policy discount even if selected. | `P0000060` (selected) and `P0000012` (not selected): base and modified 156000 in both. | proven |
| R-ST-51 | When multi-policy is not selected, GL and PR receive no package discount. | `P0000001` (GL) and `P0000006` (PR): base and modified stay at 87150 and 57000, respectively, in both. | proven |

## [`InsQuoteEngine>>endorsements:premium:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L173-L187) and [`wholeDollars:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L190-L192)
No COBOL endorsement paragraph; compare the total calculation in [`RATEPREM.cbl:3600-POLICY-FEE`, 471–473](../cobol/RATEPREM.cbl#L471-L473). Positive endorsement examples below compare Pharo's reported endorsement charge with COBOL's total, which adds only the fee to the modified premium. The cap sees the sum before the fee.

| ID | Statement | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- |
| R-ST-52 | GL adds $50 per additional insured for counts from one through three before the aggregate cap. | `P0000076`: one, endorsements 5000; Pharo total 440344 vs COBOL 435344. | amber: quote-only charge |
| R-ST-53 | GL counts no more than three additional insureds. | `P0000075`: four with no other endorsement, Pharo 15000; total 1473999 vs COBOL 1458999. | amber: quote-only charge |
| R-ST-54 | A negative GL count of additional insureds is treated as zero. | No fixture reaches this; POLREC represents the count as unsigned. | unproven |
| R-ST-55 | Lines other than GL do not charge for additional insureds. | No fixture reaches this with a positive non-GL count. | unproven |
| R-ST-56 | Selected PR equipment breakdown costs $75 when 3% of modified premium is below that amount before whole-dollar rounding. | `P0000070`: modified 35000, Pharo endorsement 7500, total 46000 vs COBOL 38500. | amber: quote-only charge |
| R-ST-57 | Selected PR equipment breakdown costs 3% of modified premium when that amount exceeds the $75 floor, rounded half up to whole dollars after cent rounding. | `P0000071`: modified 416000 gives 12480 cents before dollar rounding; Pharo endorsement 12500, total 432000 vs COBOL 419500. | amber: quote-only charge |
| R-ST-58 | A selected equipment breakdown flag does not add a charge outside PR. | `P0000073` reaches the line guard on GL, but the aggregate cap masks any observable effect of equipment exclusion. | unproven |
| R-ST-59 | A selected waiver adds 2% of modified premium on GL or CA, rounded half up to whole dollars after cent rounding. | `P0000120` (GL): modified 685801, Pharo endorsement 13700, total 703001 vs 689301; `P0000072` (CA): modified 305000, Pharo endorsement 6100, total 314600 vs 308500. | amber: quote-only charge |
| R-ST-60 | A selected waiver does not add a charge on PR. | No fixture reaches this with the waiver selected. | unproven |
| R-ST-61 | Selected hired and non-owned auto coverage adds $120 on GL before the aggregate cap. | `P0000085`: Pharo endorsement 12000, total 129048 vs COBOL 117048. | amber: quote-only charge |
| R-ST-62 | Selected hired and non-owned auto coverage does not add a charge outside GL. | `P0000072`: CA with waiver and hired/non-owned flags selected; Pharo endorsement 6100 equals the waiver alone, not 18100, and COBOL charges neither. | proven |
| R-ST-63 | When positive endorsement charges do not exceed the cap, add the full sum to the quote. | `P0000068`: 10000 additional insureds plus 2500 waiver gives Pharo endorsement 12500, below cap 31125; total 140500 vs COBOL 128000. | amber: quote-only charges |
| R-ST-64 | Cap the combined endorsement charge at 25% of modified premium, rounded half up to the cent. | `P0000073`: 28000 computed before cap, Pharo endorsement 12650 on modified 50600, total 66750 vs COBOL 54100. `P0000170` also exercises cent rounding: 25% of 72373 gives 18093.25 cents, output 18093. | amber: quote-only cap |

## [`InsQuoteEngine>>policyFee`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L195)
COBOL: [`RATEPREM.cbl:3600-POLICY-FEE`, 471–473](../cobol/RATEPREM.cbl#L471-L473), with fee constant at [line 75](../cobol/RATEPREM.cbl#L75).

| ID | Statement | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- |
| R-ST-65 | Charge a flat $35 fee on a successful policy quote. | `P0000001`: modified 87150, fee 3500 and total 90650 in both. | proven |

## Cross-check handoff

| Group | Paired keys, exclusivity, fallback and unused rows |
| --- | --- |
| Eligibility | Line + class restrict both state passes. `P0000040`/ `P0000041` isolate state, and `P0000040`/ `P0000042` separate classes in CA/NY. Exact state, wildcard and no match are exclusive outcomes. No fixture reaches simultaneous exact and wildcard candidates; every shipped row is used. |
| Class | Line + class + date; R-ST-12/13 exercise consecutive, non-overlapping rows. `tables/class-factors.dat:8,12` are blocked by eligibility (`P0000005`, `P0000009`); line 16 is blocked by line validation (`P0000013`): no fixture reaches these rate rows. |
| Territory | Line + territory + date; exact and 000 fallback cannot both win, e.g. `P0000014` (requested 000, T) vs `P0000018` (missing 099, D) with the same effective factor. `tables/territory-factors.dat:12` (PR/060) is never selected: `P0000023` uses fallback 000 even with a known requested territory. All other territory rows produce a final T or D in at least one fixture. |
| Override | Line + class + requested territory + date; O replaces T/D rather than stacking. R-ST-20–24 cover all three shipped rows plus incomplete keys/date misses. No fixture reaches replacing a default D or competing matching overrides with these rows. |
| Minimum | Line + state; `P0000061`/ `P0000062` distinguish exact from wildcard and `P0000121` shows GL/CA cannot leak into a CA line policy in the same state. `tables/minimum-premium.dat:8` is unreachable: `P0000013` is rejected as WC before rating. |
| Ranges | Class/territory/override each requires an inclusive date window, with an open end if blank. Experience and deductible tiers, as well as the lower, middle and upper schedule cases, are each mutually exclusive by their conditions. |
| COBOL-only counterpart | `RATEPREM.cbl:3450-WIND-SURCHARGE`, 433–443, has no Pharo step. It searches for PR/WND, which has no row in `tables/territory-factors.dat:3–15`; `P0000101` (PR/FL) executes with a neutral result in both. No fixture reaches a non-neutral WND factor. |
