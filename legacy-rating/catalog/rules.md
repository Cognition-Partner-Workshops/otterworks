# Legacy rating rule catalog

COBOL batch and Pharo quote behavior on `demo-insrules` at `3d1c5662441923c6361912e088f2f9c60ae6d6e9`.
Section headings group the matching paragraph and method; their citations apply to every entry in the section.
See [citation and evidence conventions](citations.md) and the [score](score.md).

## Effective dates — open end and in-force comparisons

**COBOL:** [`RATEPREM.cbl:0130-OPEN-END-DATE`, 224–229](../cobol/RATEPREM.cbl#L224-L229). **Pharo:** [`InsRatingTables>>row:from:inForceOn:`, 46–53](../smalltalk/src/InsRating/InsRatingTables.class.st#L46-L53).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R01 | A blank end date leaves the row in force from its start without an expiry. | both | [`RATEPREM.cbl:2100-LOOKUP-CLASS`, 322–325](../cobol/RATEPREM.cbl#L322-L325); [`tables/class-factors.dat:6`](../tables/class-factors.dat#L6); [`tables/territory-factors.dat:3`](../tables/territory-factors.dat#L3); [`tables/overrides.dat:4`](../tables/overrides.dat#L4) | `P0000128` uses open-ended GL/41650 and GL/000 in September (286979/T); `P0000035` uses open-ended PR/0702/030 (341120/O), in both. | proven |
| R02 | A row is in force on both its start date and its stated end date. | both | [`RATEPREM.cbl:2300-LOOKUP-OVERRIDE`, 372–376](../cobol/RATEPREM.cbl#L372-L376); [`tables/overrides.dat:4–5`](../tables/overrides.dat#L4-L5) | `P0000034`/ `P0000035` switch T to O at the start; `P0000037`/ `P0000038` switch O to T only after the end, in both. | proven |

## Rating dispatch and validation

**COBOL:** [`RATEPREM.cbl:1000-RATE-POLICY`, 231–262](../cobol/RATEPREM.cbl#L231-L262). **Pharo:** [`InsQuoteEngine>>quote:`, 28–40](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L28-L40).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R03 | Once a validation or lookup rejects or declines a policy, rating stops and no premium or fee is charged. | both | Section source | `P0000013` and `P0000040`: respectively REJ/LN and DEC/EX04, with no base, fee or total in either stack (all zero). | proven |

## Line validation

**COBOL:** [`RATEPREM.cbl:1100-VALIDATE-LINE`, 276–281](../cobol/RATEPREM.cbl#L276-L281). **Pharo:** [`InsQuoteEngine>>validateLine:into:`, 59–61](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L59-L61).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R04 | GL, PR and CA pass line validation and proceed to exposure validation. | both | Section source | `P0000001` (GL), `P0000006` (PR) and `P0000010` (CA): OK in both. | proven |
| R05 | Reject a line other than GL, PR or CA with LN. | both | Section source | `P0000013`: WC is REJ/LN in both despite WC class and minimum table records. | proven |

## Exposure validation

**COBOL:** [`RATEPREM.cbl:1200-VALIDATE-EXPOSURE`, 283–287](../cobol/RATEPREM.cbl#L283-L287). **Pharo:** [`InsQuoteEngine>>validateExposure:into:`, 64–66](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L64-L66).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R06 | Once the line is accepted, reject exposure of zero or less with EX. | both | Section source | `P0000043` (negative) and `P0000044` (zero): both stacks REJ/EX. | proven |

## Eligibility selection

**COBOL:** [`RATEPREM.cbl:2000-CHECK-ELIGIBILITY`, 291–310](../cobol/RATEPREM.cbl#L291-L310). **Pharo:** [`InsQuoteEngine>>checkEligibility:into:`, 69–77](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L69-L77).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R07 | Select the first exact-state eligibility row for the policy line and class when there is no competing all-state row. | both | [`tables/line-eligibility.dat:5`](../tables/line-eligibility.dat#L5) | `P0000040` (CA/7219/NY) is DEC/EX04, but `P0000041` (CA/7219/IL) is OK in both. | proven |
| R08 | Prefer the exact-state row when both exact and all-states rows match the same line and class. | both | [`tables/line-eligibility.dat:3–6`](../tables/line-eligibility.dat#L3-L6) | No fixture reaches this: no pair has both rows. | unproven |
| R09 | When no exact-state row matches the line and class, use the matching all-states row. | both | [`tables/line-eligibility.dat:3–4`](../tables/line-eligibility.dat#L3-L4); [`tables/line-eligibility.dat:6`](../tables/line-eligibility.dat#L6) | `P0000005`: GL/91111/IL gets wildcard EX01; `P0000009`: PR/0567/IL gets wildcard EX02 in both. | proven |
| R10 | When neither the exact-state nor all-states row matches the line and class, do not decline for eligibility. | both | [`tables/line-eligibility.dat:5`](../tables/line-eligibility.dat#L5) | `P0000041` is OK in both; only NY has a row for its CA/7219 pair. | proven |

## Eligibility decisions

**COBOL:** [`RATEPREM.cbl:2010-APPLY-ELIGIBILITY`, 312–316](../cobol/RATEPREM.cbl#L312-L316). **Pharo:** [`InsQuoteEngine>>checkEligibility:into:`, 69–77](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L69-L77).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R11 | An eligibility row marked N declines the policy with that row's reason. | both | [`tables/line-eligibility.dat:3–5`](../tables/line-eligibility.dat#L3-L5) | `P0000005`: DEC/EX01; `P0000009`: DEC/EX02; `P0000040`: DEC/EX04 in both. | from-table |
| R12 | An eligibility row not marked N does not decline the policy. | both | [`tables/line-eligibility.dat:6`](../tables/line-eligibility.dat#L6) | `P0000042` and `P0000012` are OK in both; there is no row trace and the same output would occur without the Y row. | unproven |
| R13 | Decline GL class 91111 in all states with EX01. | both | [`tables/line-eligibility.dat:3`](../tables/line-eligibility.dat#L3) | `P0000005`: DEC/EX01 in both. | from-table |
| R14 | Decline PR class 0567 in all states with EX02. | both | [`tables/line-eligibility.dat:4`](../tables/line-eligibility.dat#L4) | `P0000009`: DEC/EX02 in both. | from-table |
| R15 | Decline CA class 7219 in NY with EX04. | both | [`tables/line-eligibility.dat:5`](../tables/line-eligibility.dat#L5) | `P0000040` (NY): DEC/EX04; `P0000041` otherwise identical in IL: OK in both. | from-table |
| R16 | Treat CA class 7911 as eligible in all states. | both | [`tables/line-eligibility.dat:6`](../tables/line-eligibility.dat#L6) | `P0000042` (NY) and `P0000012` (IL) match the Y row and rate in both; removing the row would leave the result unchanged. | unproven |

## Class rate

**COBOL:** [`RATEPREM.cbl:2100-LOOKUP-CLASS`, 318–335](../cobol/RATEPREM.cbl#L318-L335). **Pharo:** [`InsQuoteEngine>>lookupClassRate:into:`, 80–87](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L80-L87).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R17 | Take the base rate from the first in-force row matching both the policy line and class. | both | [`tables/class-factors.dat:3`](../tables/class-factors.dat#L3); [`tables/class-factors.dat:9`](../tables/class-factors.dat#L9) | `P0000001` (GL/91340) and `P0000006` (PR/0311) select 4.1500 and 0.3800 respectively from the paired keys; bases 87150 and 57000 in both. No fixture isolates ordering between duplicate in-force rows: there are none. | proven |
| R18 | Reject with CL when there is no in-force row for the policy's line and class. | both | [`tables/class-factors.dat:3–16`](../tables/class-factors.dat#L3-L16) | No fixture reaches this; all 190 policies reaching class lookup match. | unproven |
| R19 | Use a GL/41650 rate of 2.1000 for effective dates from January 1 through June 30, 2026. | both | [`tables/class-factors.dat:5`](../tables/class-factors.dat#L5) | `P0000028` on June 30: base 79800 at factor 0.950 in both. | from-table |
| R20 | Use a GL/41650 rate of 2.2500 from July 1, 2026 onward. | both | [`tables/class-factors.dat:6`](../tables/class-factors.dat#L6) | `P0000030` on July 1: base 85500 at factor 0.950 in both. | from-table |
| R21 | Use a base rate of 4.1500 for GL/91340 from January 1, 2026. | both | [`tables/class-factors.dat:3`](../tables/class-factors.dat#L3) | `P0000001`: base 87150. | from-table |
| R22 | Use a base rate of 6.2000 for GL/91580 from January 1, 2026. | both | [`tables/class-factors.dat:4`](../tables/class-factors.dat#L4) | `P0000002`: base 130200. | from-table |
| R23 | Use a base rate of 1.1000 for GL/18501 from January 1, 2026. | both | [`tables/class-factors.dat:7`](../tables/class-factors.dat#L7) | `P0000004`: base 23100. | from-table |
| R24 | The table lists a base rate of 9.7500 for GL/91111 from January 1, 2026, but eligibility preempts it. | both | [`tables/class-factors.dat:8`](../tables/class-factors.dat#L8); [`tables/line-eligibility.dat:3`](../tables/line-eligibility.dat#L3) | No fixture reaches this rate row; `P0000005` declines EX01 before class lookup. | unproven |
| R25 | Use a base rate of 0.3800 for PR/0311 from January 1, 2026. | both | [`tables/class-factors.dat:9`](../tables/class-factors.dat#L9) | `P0000006`: base 57000. | from-table |
| R26 | Use a base rate of 0.5200 for PR/0702 from January 1, 2026. | both | [`tables/class-factors.dat:10`](../tables/class-factors.dat#L10) | `P0000007`: base 78000. | from-table |
| R27 | Use a base rate of 0.7100 for PR/0900 from January 1, 2026. | both | [`tables/class-factors.dat:11`](../tables/class-factors.dat#L11) | `P0000008`: base 106500. | from-table |
| R28 | The table lists a base rate of 0.4400 for PR/0567 from January 1, 2026, but eligibility preempts it. | both | [`tables/class-factors.dat:12`](../tables/class-factors.dat#L12); [`tables/line-eligibility.dat:4`](../tables/line-eligibility.dat#L4) | No fixture reaches this rate row; `P0000009` declines EX02 before class lookup. | unproven |
| R29 | Use a base rate of 610.0000 for CA/7398 from January 1, 2026. | both | [`tables/class-factors.dat:13`](../tables/class-factors.dat#L13) | `P0000010`: base 183000. | from-table |
| R30 | Use a base rate of 1450.0000 for eligible CA/7219 from January 1, 2026. | both | [`tables/class-factors.dat:14`](../tables/class-factors.dat#L14); [`tables/line-eligibility.dat:5`](../tables/line-eligibility.dat#L5) | `P0000041` (IL): base 435000; `P0000040` (NY) declines EX04 instead. | from-table |
| R31 | Use a base rate of 520.0000 for CA/7911 from January 1, 2026. | both | [`tables/class-factors.dat:15`](../tables/class-factors.dat#L15) | `P0000012`: base 156000. | from-table |
| R32 | The table lists a base rate of 0.2500 for WC/8810 from January 1, 2026, but line validation preempts it. | both | [`tables/class-factors.dat:16`](../tables/class-factors.dat#L16) | No fixture reaches this rate row; `P0000013` rejects LN before class lookup. | unproven |

## Territory factor

**COBOL:** [`RATEPREM.cbl:2200-LOOKUP-TERRITORY`, 338–365](../cobol/RATEPREM.cbl#L338-L365). **Pharo:** [`InsQuoteEngine>>lookupTerritory:into:`, 90–104](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L90-L104).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R33 | An in-force row for the policy's line and requested territory supplies its territory factor and marks the source T. | both | [`tables/territory-factors.dat:3`](../tables/territory-factors.dat#L3); [`tables/territory-factors.dat:6`](../tables/territory-factors.dat#L6); [`tables/territory-factors.dat:11`](../tables/territory-factors.dat#L11) | `P0000017` (GL/040) gets 1.200/T and `P0000022` (PR/040) gets 1.150/T; `P0000001` explicitly requests 000 and still gets T. | proven |
| R34 | If the requested territory has no in-force row, use that line's in-force 000 row and mark the source D. | both | [`tables/territory-factors.dat:3`](../tables/territory-factors.dat#L3); [`tables/territory-factors.dat:8`](../tables/territory-factors.dat#L8); [`tables/territory-factors.dat:12`](../tables/territory-factors.dat#L12) | `P0000018` (missing 099) gets 1.000/D, base 74700; `P0000023` (expired PR/060) gets 1.000/D, base 45600 in both. | proven |
| R35 | If neither the requested territory nor the 000 fallback is in force for the line, reject with TR. | both | [`tables/territory-factors.dat:3`](../tables/territory-factors.dat#L3); [`tables/territory-factors.dat:8`](../tables/territory-factors.dat#L8); [`tables/territory-factors.dat:13`](../tables/territory-factors.dat#L13) | No fixture reaches this; an in-force 000 row covers every in-force class date on each allowed line. | unproven |
| R36 | Use a GL/040 factor of 1.200 for effective dates from January 1 through June 30, 2026. | both | [`tables/territory-factors.dat:6`](../tables/territory-factors.dat#L6) | `P0000027` on June 30: source T, base 149400 in both. | from-table |
| R37 | Use a GL/040 factor of 1.350 from July 1, 2026 onward. | both | [`tables/territory-factors.dat:7`](../tables/territory-factors.dat#L7) | `P0000029` on July 1: source T, base 168075 in both. | from-table |
| R38 | From January 1, 2026 onward, use factor 1.000 for GL/000, whether explicitly requested or selected as the GL fallback. | both | [`tables/territory-factors.dat:3`](../tables/territory-factors.dat#L3) | `P0000014`: 74700/T; `P0000018`: 74700/D. | from-table |
| R39 | From January 1, 2026 onward, use factor 0.950 for GL/010. | both | [`tables/territory-factors.dat:4`](../tables/territory-factors.dat#L4) | `P0000015`: 70965/T. | from-table |
| R40 | From January 1, 2026 onward, use factor 1.100 for GL/020. | both | [`tables/territory-factors.dat:5`](../tables/territory-factors.dat#L5) | `P0000016`: 82170/T. | from-table |
| R41 | From January 1, 2026 onward, use factor 1.000 for PR/000, whether explicitly requested or selected as the PR fallback. | both | [`tables/territory-factors.dat:8`](../tables/territory-factors.dat#L8) | `P0000019`: 45600/T; `P0000023`: 45600/D. | from-table |
| R42 | From January 1, 2026 onward, use factor 0.900 for PR/010. | both | [`tables/territory-factors.dat:9`](../tables/territory-factors.dat#L9) | `P0000020`: 41040/T. | from-table |
| R43 | From January 1, 2026 onward, use factor 1.250 for PR/030 when there is no override. | both | [`tables/territory-factors.dat:10`](../tables/territory-factors.dat#L10) | `P0000021`: 57000/T. | from-table |
| R44 | From January 1, 2026 onward, use factor 1.150 for PR/040. | both | [`tables/territory-factors.dat:11`](../tables/territory-factors.dat#L11) | `P0000022`: 52440/T. | from-table |
| R45 | The table lists PR/060 at 1.400 for January 1–December 31, 2025, but no in-force PR class overlaps that interval. | both | [`tables/territory-factors.dat:12`](../tables/territory-factors.dat#L12); [`tables/class-factors.dat:9–12`](../tables/class-factors.dat#L9-L12) | No fixture reaches this factor; all PR class rows start in 2026, and `P0000023` takes 000/D instead. | unproven |
| R46 | From January 1, 2026 onward, use factor 1.000 when CA/000 is explicitly requested. | both | [`tables/territory-factors.dat:13`](../tables/territory-factors.dat#L13) | `P0000024`: 122000/T. No fixture reaches the same row as fallback D. | from-table |
| R47 | From January 1, 2026 onward, use factor 1.300 for CA/020 when there is no override. | both | [`tables/territory-factors.dat:14`](../tables/territory-factors.dat#L14) | `P0000025`: 158600/T. | from-table |
| R48 | From January 1, 2026 onward, use factor 0.850 for CA/050. | both | [`tables/territory-factors.dat:15`](../tables/territory-factors.dat#L15) | `P0000026`: 103700/T. | from-table |

## Territory override

**COBOL:** [`RATEPREM.cbl:2300-LOOKUP-OVERRIDE`, 368–382](../cobol/RATEPREM.cbl#L368-L382). **Pharo:** [`InsQuoteEngine>>lookupOverride:into:`, 107–117](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L107-L117).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R49 | The first in-force override for the exact line, class and requested territory replaces the prior factor without multiplying it and marks the source O. | both | [`tables/overrides.dat:3–5`](../tables/overrides.dat#L3-L5); [`tables/territory-factors.dat:6–7`](../tables/territory-factors.dat#L6-L7); [`tables/territory-factors.dat:10`](../tables/territory-factors.dat#L10); [`tables/territory-factors.dat:14`](../tables/territory-factors.dat#L14) | `P0000031` and `P0000032`: different underlying territory factors but the same O and base 139965 in both. No fixture reaches competing overrides; the table has no duplicates. | proven |
| R50 | When no in-force override matches all keys, retain the selected territory factor and its original source. | both | [`tables/overrides.dat:3–5`](../tables/overrides.dat#L3-L5); [`tables/territory-factors.dat:3`](../tables/territory-factors.dat#L3); [`tables/territory-factors.dat:5–6`](../tables/territory-factors.dat#L5-L6); [`tables/territory-factors.dat:10`](../tables/territory-factors.dat#L10); [`tables/territory-factors.dat:14`](../tables/territory-factors.dat#L14) | `P0000017` (wrong class), `P0000033` (wrong territory), `P0000034` (before start), `P0000038` (after end) retain T; `P0000018` retains D in both. | proven |
| R51 | Use override factor 1.500 for GL/91580/040 effective January 1 through December 31, 2026. | both | [`tables/overrides.dat:3`](../tables/overrides.dat#L3) | `P0000031`, `P0000032` (last day): O, base 139965 in both. | from-table |
| R52 | Use override factor 1.600 for PR/0702/030 effective March 1, 2026 onward. | both | [`tables/overrides.dat:4`](../tables/overrides.dat#L4) | `P0000035` (first day): O, base 341120 in both. | from-table |
| R53 | Use override factor 1.550 for CA/7219/020 effective January 1 through September 30, 2026. | both | [`tables/overrides.dat:5`](../tables/overrides.dat#L5) | `P0000037` (last day): O, base 899000 in both. | from-table |

## Base premium

**COBOL:** [`RATEPREM.cbl:3000-BASE-PREMIUM`, 384–387](../cobol/RATEPREM.cbl#L384-L387). **Pharo:** [`InsQuoteEngine>>basePremium:quote:`, 120–124](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L120-L124); [`InsQuoteEngine>>round:scale:`, 22–25](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L22-L25).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R54 | Multiply exposure by the base rate and round half up to the cent before applying the territory factor. | both | Section source | `P0000120`: exposure times rate yields 577516.5 cents, factor 1.000, base 577517 in both. `P0000092`: both give 45097; rounding only after both multiplications would give 45098. | proven |
| R55 | Multiply the rounded amount by the selected territory factor and round half up to the cent for base premium. | both | Section source | `P0000065`: 55550 × 0.950 = 52772.5 cents, base 52773 in both. | proven |

## Experience modifier

**COBOL:** [`RATEPREM.cbl:3100-EXPERIENCE-MOD`, 389–398](../cobol/RATEPREM.cbl#L389-L398). **Pharo:** [`InsQuoteEngine>>experienceMod:premium:`, 127–133](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L127-L133).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R56 | Increase premium by 25% for three or more claims in the last three years. | both | Section source | `P0000047`: 3 claims, base 86735 to modified 108419 in both. | proven |
| R57 | Reduce premium by 10% for zero claims and at least three years in business. | both | Section source | `P0000045`: 0 claims, 3 years, base 86735 to modified 78062 in both. | proven |
| R58 | Otherwise leave the premium unchanged by experience. | both | Section source | `P0000046`: 0 claims, 2 years, base and modified 86735; `P0000001`: 1 claim, 5 years, base and modified 87150 in both. | proven |

## Deductible credit

**COBOL:** [`RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT`, 401–413](../cobol/RATEPREM.cbl#L401-L413). **Pharo:** [`InsQuoteEngine>>deductibleCredit:premium:`, 136–144](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L136-L144).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R59 | GL receives no deductible credit. | both | Section source | `P0000053`: GL, $5,000 deductible, base and modified 72600 in both. | proven |
| R60 | For PR or CA, a deductible of at least $5,000 earns an 8% credit. | both | Section source | `P0000051` PR: 57510 to 52909; `P0000052` CA: 155550 to 143106 in both. | proven |
| R61 | For PR or CA, a deductible from $2,500 up to but not including $5,000 earns a 5% credit. | both | Section source | `P0000050`: $2,500, base 57510 to modified 54635 in both. | proven |
| R62 | For PR or CA, a deductible from $1,000 up to but not including $2,500 earns a 2% credit. | both | Section source | `P0000049`: $1,000, base 57510 to modified 56360 in both. | proven |
| R63 | For PR or CA, a deductible below $1,000 earns no credit. | both | Section source | `P0000048`: $999, base and modified 57510 in both. | proven |

## Schedule modifier

**COBOL:** [`RATEPREM.cbl:3300-SCHEDULE-MOD`, 415–423](../cobol/RATEPREM.cbl#L415-L423). **Pharo:** [`InsQuoteEngine>>scheduleMod:premium:`, 160–164](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L160-L164).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R64 | A schedule adjustment below −25% is applied as −25%. | both | Section source | `P0000054` (−30%) and `P0000055` (−25%): identical base 73040 and modified 54780 in both. | proven |
| R65 | A schedule adjustment above +25% is applied as +25%. | both | Section source | `P0000057` (+40%): 73040 to 91300 in both. | proven |
| R66 | A schedule adjustment between −25% and +25% inclusive applies as entered, with zero leaving the premium unchanged. | both | Section source | `P0000056` (+15%): 73040 to 83996; `P0000080` (−20%): 155139 to 124111; `P0000001` (0): unchanged in both. | proven |

## Multi-policy credit

**COBOL:** [`RATEPREM.cbl:3400-MULTI-POLICY`, 425–429](../cobol/RATEPREM.cbl#L425-L429). **Pharo:** [`InsQuoteEngine>>multiPolicy:premium:`, 167–170](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L167-L170).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R67 | On GL or PR with a selected multi-policy discount, round the schedule-adjusted premium to cents before applying the 5% discount, then round again to cents. | both | [`RATEPREM.cbl:1000-RATE-POLICY`, 257–258](../cobol/RATEPREM.cbl#L257-L258); [`RATEPREM.cbl:3300-SCHEDULE-MOD`, 415–423](../cobol/RATEPREM.cbl#L415-L423); [`InsQuoteEngine>>rate:into:`, 43–56](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L43-L56); [`InsQuoteEngine>>scheduleMod:premium:`, 160–164](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L160-L164); [`InsQuoteEngine>>round:scale:`, 22–25](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L22-L25) | `P0000058` (GL): 88000 to 83600; `P0000059` (PR): 76000 to 72200 in both. For `P0000076` (GL), the 5% schedule increase rounds 432927 to 454573 before the discount; both stacks output 431844, not the 431845 from rounding only once. | proven |
| R68 | CA does not receive a multi-policy discount even if selected. | both | Section source | `P0000060` (selected) and `P0000012` (not selected): base and modified 156000 in both. | proven |
| R69 | When multi-policy is not selected, GL and PR receive no package discount. | both | Section source | `P0000001` (GL) and `P0000006` (PR): base and modified stay at 87150 and 57000, respectively, in both. | proven |

## Florida property wind

**COBOL:** [`RATEPREM.cbl:3450-WIND-SURCHARGE`, 433–443](../cobol/RATEPREM.cbl#L433-L443). **Pharo:** [`InsQuoteEngine>>rate:into:`, 43–56](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L43-L56) (no wind step).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R70 | Florida PR uses the last PR/WND territory row as a separate wind multiplier regardless of its effective dates. | COBOL only | [`tables/territory-factors.dat:8–12`](../tables/territory-factors.dat#L8-L12) (PR rows searched; none is WND) | No fixture reaches this: Florida PR is present but the required row is absent. | unproven |
| R71 | Florida PR with no PR/WND row keeps the wind multiplier at 1.000. | COBOL only | [`tables/territory-factors.dat:8–12`](../tables/territory-factors.dat#L8-L12) (PR rows searched; none is WND) | `P0000101` (PR/FL): base 430652 and modified 538315 in both; the neutral result cannot distinguish COBOL's fallback from Pharo skipping the lookup. | unproven |

## Minimum selection and application

**COBOL:** [`RATEPREM.cbl:3500-MINIMUM-PREMIUM`, 446–469](../cobol/RATEPREM.cbl#L446-L469). **Pharo:** [`InsQuoteEngine>>applyMinimum:premium:quote:`, 147–157](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L147-L157).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R72 | The first minimum row matching the policy's line and state wins over the all-state minimum for the same line. | both | [`tables/minimum-premium.dat:3–4`](../tables/minimum-premium.dat#L3-L4); [`tables/minimum-premium.dat:6–7`](../tables/minimum-premium.dat#L6-L7) | `P0000061` (GL/CA) applies 75000 rather than 50000; `P0000063` (CA/TX) applies 120000 rather than 100000, in both. | proven |
| R73 | If no exact state minimum matches, the first all-state minimum for the same line is used. | both | [`tables/minimum-premium.dat:3`](../tables/minimum-premium.dat#L3); [`tables/minimum-premium.dat:5–6`](../tables/minimum-premium.dat#L5-L6) | `P0000062` (GL/IL) applies 50000; [`P0000064` (PR/FL)](../fixtures/policies.dat#L64) applies 35000, in both. | proven |
| R74 | Apply a $750 minimum in California for GL rather than the GL all-states minimum. | both | [`tables/minimum-premium.dat:3–4`](../tables/minimum-premium.dat#L3-L4) | `P0000061` (CA) and `P0000062` (IL) both start at 44000; both stacks floor to 75000 and 50000 respectively. | from-table |
| R75 | Apply a $1,200 minimum in Texas for CA rather than the CA all-states minimum. | both | [`tables/minimum-premium.dat:6–7`](../tables/minimum-premium.dat#L6-L7) | `P0000026`: 103700 to 120000 with minimum Y in both, above the 100000 wildcard. | from-table |
| R76 | When there is no state-specific minimum for GL use $500. | both | [`tables/minimum-premium.dat:3`](../tables/minimum-premium.dat#L3) | `P0000062`: 44000 to 50000 with minimum Y in both. | from-table |
| R77 | When there is no state-specific minimum for PR use $350. | both | [`tables/minimum-premium.dat:5`](../tables/minimum-premium.dat#L5) | `P0000064`: 27360 to 35000 with minimum Y in both. | from-table |
| R78 | When there is no state-specific minimum for CA use $1,000. | both | [`tables/minimum-premium.dat:6`](../tables/minimum-premium.dat#L6) | `P0000121` (CA policy in California): 88400 base; both report 100000 modified with minimum Y. | from-table |
| R79 | If neither a state-specific nor all-states minimum matches the policy line, impose no minimum. | both | [`tables/minimum-premium.dat:3–8`](../tables/minimum-premium.dat#L3-L8) | No fixture reaches this: each permitted line has an all-states row. | unproven |
| R80 | Raise premium to the selected minimum and mark it applied only when the current premium is lower. | both | [`tables/minimum-premium.dat:3`](../tables/minimum-premium.dat#L3) | `P0000062`: 44000 to 50000/Y; `P0000001`: 87150 unchanged/N, in both. No fixture reaches exact equality. | proven |
| R81 | The table lists a $250 minimum for WC in all states, but line validation preempts it. | both | [`tables/minimum-premium.dat:8`](../tables/minimum-premium.dat#L8) | No fixture reaches this minimum; `P0000013` rejects LN with minimum N in both. | unproven |

## Minimum order — legacy disagreement

**COBOL:** [`RATEPREM.cbl:1000-RATE-POLICY`, 252–262](../cobol/RATEPREM.cbl#L252-L262). **Pharo:** [`InsQuoteEngine>>rate:into:`, 43–56](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L43-L56); [`InsQuoteEngine>>applyMinimum:premium:quote:`, 147–157](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L147-L157).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R82 | COBOL applies the minimum after schedule and multi-policy adjustments, whereas Pharo applies it before both. | both | [`RATEPREM.cbl:3500-MINIMUM-PREMIUM`, 465–469](../cobol/RATEPREM.cbl#L465-L469); [`tables/minimum-premium.dat:3–6`](../tables/minimum-premium.dat#L3-L6) | `P0000065`: COBOL 50000/Y vs Pharo 40107/N; `P0000066`: 35000/Y vs 28263/Y; `P0000067`: 55440/N vs 60000/Y; `P0000082`: 100000/Y vs 125000/Y; `P0000200`: 75000/Y vs 67500/Y. The same floor rows are selected; order changes the premium or flag. | amber |

## Policy fee and total

**COBOL:** [`RATEPREM.cbl:3600-POLICY-FEE`, 471–473](../cobol/RATEPREM.cbl#L471-L473). **Pharo:** [`InsQuoteEngine>>policyFee`, 195](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L195); [`InsQuoteEngine>>rate:into:`, 43–56](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L43-L56).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R83 | Charge a flat $35 fee on a successful policy quote. | both | [`RATEPREM.cbl:WS-POLICY-FEE`, 75](../cobol/RATEPREM.cbl#L75) | `P0000001`: modified 87150, fee 3500 and total 90650 in both. | proven |
| R84 | COBOL totals modified premium plus the fee, whereas Pharo also adds the endorsement charge. | both | [`RATEPREM.cbl:1000-RATE-POLICY`, 252–262](../cobol/RATEPREM.cbl#L252-L262) | `P0000071`: both modify to 416000 and charge a 3500 fee; COBOL totals 419500, Pharo adds 12500 and totals 432000. | amber |

## Endorsement charges

**COBOL:** [`RATEPREM.cbl:1000-RATE-POLICY`, 252–262](../cobol/RATEPREM.cbl#L252-L262); [`RATEPREM.cbl:3600-POLICY-FEE`, 471–473](../cobol/RATEPREM.cbl#L471-L473) (no endorsement step). **Pharo:** [`InsQuoteEngine>>endorsements:premium:`, 173–187](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L173-L187); [`InsQuoteEngine>>wholeDollars:`, 190–192](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L190-L192); [`InsQuoteEngine>>round:scale:`, 22–25](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L22-L25).

| Rule | Statement | Scope | Specific citations | Proving fixture or evidence gap | Status |
| --- | --- | --- | --- | --- | --- |
| R85 | GL adds $50 per additional insured for counts from one through three before the aggregate cap. | Pharo only | Section source | `P0000076`: one, endorsements 5000; Pharo total 440344 vs COBOL 435344. COBOL has no endorsement step (see R84). | amber |
| R86 | GL counts no more than three additional insureds. | Pharo only | Section source | `P0000075`: four with no other endorsement, Pharo 15000; total 1473999 vs COBOL 1458999. COBOL has no endorsement step (see R84). | amber |
| R87 | A negative GL count of additional insureds is treated as zero. | Pharo only | Section source | No fixture reaches this; POLREC represents the count as unsigned. | unproven |
| R88 | Lines other than GL do not charge for additional insureds. | Pharo only | Section source | No fixture reaches this with a positive non-GL count. | unproven |
| R89 | Selected PR equipment breakdown costs $75 when the cent-rounded 3% charge is at or below $75. | Pharo only | Section source | `P0000070`: modified 35000, Pharo endorsement 7500, total 46000 vs COBOL 38500. No fixture reaches equality. COBOL has no endorsement step (see R84). | amber |
| R90 | Selected PR equipment breakdown costs the cent-rounded 3% of modified premium, rounded half up to whole dollars, when that charge exceeds $75 before whole-dollar rounding. | Pharo only | Section source | `P0000071`: modified 416000 gives 12480 cents before dollar rounding; Pharo endorsement 12500, total 432000 vs COBOL 419500. COBOL has no endorsement step (see R84). | amber |
| R91 | A selected equipment breakdown flag does not add a charge outside PR. | Pharo only | Section source | `P0000073` reaches the line guard on GL, but the aggregate cap masks any observable effect of equipment exclusion. | unproven |
| R92 | A selected waiver adds 2% of modified premium on GL or CA, rounded half up to whole dollars after cent rounding. | Pharo only | Section source | `P0000120` (GL): modified 685801, Pharo endorsement 13700, total 703001 vs 689301; `P0000072` (CA): modified 305000, Pharo endorsement 6100, total 314600 vs 308500. COBOL has no endorsement step (see R84). | amber |
| R93 | A selected waiver does not add a charge on PR. | Pharo only | Section source | No fixture reaches this with the waiver selected. | unproven |
| R94 | Selected hired and non-owned auto coverage adds $120 on GL before the aggregate cap. | Pharo only | Section source | `P0000085`: Pharo endorsement 12000, total 129048 vs COBOL 117048. COBOL has no endorsement step (see R84). | amber |
| R95 | Selected hired and non-owned auto coverage does not add a charge outside GL. | Pharo only | Section source | `P0000072`: CA with waiver and hired/non-owned flags selected; Pharo endorsement 6100 equals the waiver alone, not 18100, and COBOL charges neither. This evidences the Pharo guard only; COBOL has no corresponding condition. | unproven |
| R96 | When positive endorsement charges do not exceed the cap, add the full sum to the quote. | Pharo only | Section source | `P0000068`: 10000 additional insureds plus 2500 waiver gives Pharo endorsement 12500, below cap 31125; total 140500 vs COBOL 128000. COBOL has no endorsement step (see R84). | amber |
| R97 | Cap the combined endorsement charge at 25% of modified premium, rounded half up to the cent. | Pharo only | Section source | `P0000073`: 28000 computed before cap, Pharo endorsement 12650 on modified 50600, total 66750 vs COBOL 54100. `P0000170` has an exact cap of 18093.25 cents and an output of 18093 under either half-up rounding or truncation. The Pharo source specifies half-up, but no fixture distinguishes the rounding mode, so the mode is unproven by execution. The cap remains amber because COBOL has no endorsement step (see R84). | amber |
| R98 | A GL quote with zero additional insureds and no selected optional endorsements adds no endorsement charge. | Pharo only | Section source | `P0000001`: Pharo prints zero endorsements, and both totals are 90650 (87150 modified + 3500 fee). This evidences the Pharo condition only; COBOL has no corresponding step. | unproven |

## Shared-table cross-check

Selections below are mutually exclusive within each lookup, not across different lookups. One policy can select a class, a territory and an override; the override replaces the territory factor rather than stacking with it.

| Lookup | Exclusivity and fallback | Paired or composite keys |
| --- | --- | --- |
| Eligibility | Exact state, all-state and no row are alternatives: `P0000040` is DEC/EX04, `P0000005` is DEC/EX01 via wildcard, and `P0000041` rates without a row. Exact wins if both exist, but no fixture reaches this: no line/class has both rows. An N row declines; `P0000042` pairs with the Y row and is OK, but the output cannot isolate Y from no row. | Line + class + state (or `**`): `P0000040` (CA/7219/NY), `P0000041` (CA/7219/IL) and `P0000042` (CA/7911/NY) vary state and class; no fixture reaches a cross-line same-class collision. |
| Class | First in-force row or CL rejection, with no default; no fixture reaches this rejection or a duplicate in-force match. `P0000028` (June 30) and `P0000030` (July 1) use nonoverlapping GL/41650 rates, yielding base 79800 and 85500. | Line + class + date: `P0000001` and `P0000003` vary class within GL; no fixture reaches a cross-line same-class collision. |
| Territory | Exact T, line default D, and TR rejection cannot coexist. `P0000014` explicitly requests 000/T; `P0000018` misses 099 and takes the same row as D; `P0000023` misses expired PR/060 and takes PR/000 as D. No fixture reaches TR or CA/000 as D. `P0000027` and `P0000029` use nonoverlapping GL/040 rates; no fixture reaches an overlap. | Line + requested territory + date: `P0000015` GL/010 = 0.950/T vs `P0000020` PR/010 = 0.900/T; `P0000016` GL/020 = 1.100/T. |
| Override | O replaces T or D; otherwise keep the existing source. `P0000031` and `P0000032` both yield 1.500/O despite different T factors. `P0000034` and `P0000038` miss on date and keep T; `P0000100` keeps D. No fixture reaches D-to-O or overlapping overrides because the shipped overrides have exact territories in force and do not overlap on a key. | Line + class + original territory + date: at fixed line GL, `P0000031` (91580/040) gets O but `P0000033` (91580/020) and `P0000027` (91340/040) retain T. No fixture reaches a cross-line same-class collision. |
| Minimum | Exact state beats wildcard: `P0000061` gets 75000 and `P0000062` falls back to 50000. If neither matches, leave premium and flag unchanged; no fixture reaches this because each accepted line has a wildcard. Applied vs not applied: `P0000062` yields 50000/Y; `P0000001` stays 87150/N. No fixture reaches exact equality. | Line + state: GL/CA (`P0000061`) and GL/IL (`P0000062`) isolate state; GL/CA and CA/CA (`P0000121`, 100000) isolate line. CA/TX (`P0000063`) takes 120000 instead of the line's 100000 wildcard. |
| Florida property wind (COBOL only) | A PR/WND match and the neutral fallback exclude each other. `P0000101` (PR/FL) has only the experience adjustment. No fixture reaches a non-neutral factor; the shipped table has no WND row. | Only PR + FL enters the lookup, and only PR + WND can supply the multiplier; no fixture reaches a non-neutral lookup or an observable bypass contrast. |

Other mutually exclusive outcomes: validation/eligibility stop versus rating (`P0000013`, `P0000040`, `P0000001`); experience debit, credit or neither (`P0000047`, `P0000045`, `P0000046`); just one deductible outcome (`P0000048`–`P0000053`); schedule low clamp, high clamp or entered value (`P0000054`, `P0000057`, `P0000056`); multi-policy discount or none (`P0000058`, `P0000060`, `P0000001`). In Pharo the PR equipment charge (`P0000070`, `P0000071`) excludes GL additional-insured and hired/non-owned auto charges and GL/CA waiver (`P0000068`, `P0000085`, `P0000072`); eligible GL charges can combine, with either the full sum (`P0000068`) or the cap (`P0000073)) applied.

### Physical table rows reached and unused

Each selected row has one witness below in both stacks. Selection is inferred from the fixture keys, preceding gates and the executed output, not a row trace. Eligibility line 6 is reached by that inference only (its Y does not change the output). A rejected policy or an expired-key fallback is not counted as selecting the skipped row.

| Table | Selected row → witness | Unused rows |
| --- | --- | --- |
| `tables/class-factors.dat` | [3](../tables/class-factors.dat#L3) → `P0000001`; [4](../tables/class-factors.dat#L4) → `P0000002`; [5](../tables/class-factors.dat#L5) → `P0000028`; [6](../tables/class-factors.dat#L6) → `P0000030`; [7](../tables/class-factors.dat#L7) → `P0000004`; [9](../tables/class-factors.dat#L9) → `P0000006`; [10](../tables/class-factors.dat#L10) → `P0000007`; [11](../tables/class-factors.dat#L11) → `P0000008`; [13](../tables/class-factors.dat#L13) → `P0000010`; [14](../tables/class-factors.dat#L14) → `P0000041`; [15](../tables/class-factors.dat#L15) → `P0000012` | [8](../tables/class-factors.dat#L8); [12](../tables/class-factors.dat#L12); [16](../tables/class-factors.dat#L16) |
| `tables/line-eligibility.dat` | [3](../tables/line-eligibility.dat#L3) → `P0000005`; [4](../tables/line-eligibility.dat#L4) → `P0000009`; [5](../tables/line-eligibility.dat#L5) → `P0000040`; [6](../tables/line-eligibility.dat#L6) → `P0000042` | — |
| `tables/territory-factors.dat` | [3](../tables/territory-factors.dat#L3) → `P0000014`; [4](../tables/territory-factors.dat#L4) → `P0000015`; [5](../tables/territory-factors.dat#L5) → `P0000016`; [6](../tables/territory-factors.dat#L6) → `P0000027`; [7](../tables/territory-factors.dat#L7) → `P0000029`; [8](../tables/territory-factors.dat#L8) → `P0000019`; [9](../tables/territory-factors.dat#L9) → `P0000020`; [10](../tables/territory-factors.dat#L10) → `P0000021`; [11](../tables/territory-factors.dat#L11) → `P0000022`; [13](../tables/territory-factors.dat#L13) → `P0000024`; [14](../tables/territory-factors.dat#L14) → `P0000025`; [15](../tables/territory-factors.dat#L15) → `P0000026` | [12](../tables/territory-factors.dat#L12) |
| `tables/overrides.dat` | [3](../tables/overrides.dat#L3) → `P0000031`; [4](../tables/overrides.dat#L4) → `P0000035`; [5](../tables/overrides.dat#L5) → `P0000037` | — |
| `tables/minimum-premium.dat` | [3](../tables/minimum-premium.dat#L3) → `P0000062`; [4](../tables/minimum-premium.dat#L4) → `P0000061`; [5](../tables/minimum-premium.dat#L5) → `P0000064`; [6](../tables/minimum-premium.dat#L6) → `P0000121`; [7](../tables/minimum-premium.dat#L7) → `P0000063` | [8](../tables/minimum-premium.dat#L8) |

- **Class rows 8 and 12:** eligibility declines `P0000005` (GL/91111) and `P0000009` (PR/0567) before class lookup; no fixture reaches these rows.
- **Class row 16 and minimum row 8:** line validation rejects WC on `P0000013`; no fixture reaches these rows.
- **Territory row 12:** PR/060 expires before any PR class starts; `P0000023` gets 000/D instead. No fixture reaches this row in force.

## Extract-to-catalog mapping

Multiple destination IDs mean the original entry covered more than one condition. A shared destination means two entries described the same condition or the two sides of one disagreement.

| COBOL extract | Catalog | Pharo extract or cross-check | Catalog |
| --- | --- | --- | --- |
| `R-COB-01` | R01 | `R-ST-01` | R03 |
| `R-COB-02` | R03 | `R-ST-02` | R05 |
| `R-COB-03` | R04 | `R-ST-03` | R06 |
| `R-COB-04` | R05 | `R-ST-04` | R13 |
| `R-COB-05` | R06 | `R-ST-05` | R14 |
| `R-COB-06` | R07, R08 | `R-ST-06` | R15 |
| `R-COB-07` | R09 | `R-ST-07` | R16 |
| `R-COB-08` | R10 | `R-ST-08` | R09 |
| `R-COB-09` | R11 | `R-ST-09` | R10 |
| `R-COB-10` | R12 | `R-ST-10` | R08 |
| `R-COB-11` | R17 | `R-ST-11` | R17 |
| `R-COB-12` | R18 | `R-ST-12` | R19 |
| `R-COB-13` | R19 | `R-ST-13` | R20 |
| `R-COB-14` | R20 | `R-ST-14` | R18 |
| `R-COB-15` | R33 | `R-ST-15` | R33 |
| `R-COB-16` | R34 | `R-ST-16` | R36 |
| `R-COB-17` | R35 | `R-ST-17` | R37 |
| `R-COB-18` | R36 | `R-ST-18` | R34 |
| `R-COB-19` | R37 | `R-ST-19` | R35 |
| `R-COB-20` | R49 | `R-ST-20` | R51 |
| `R-COB-21` | R50 | `R-ST-21` | R52 |
| `R-COB-22` | R51 | `R-ST-22` | R53 |
| `R-COB-23` | R52 | `R-ST-23` | R49 |
| `R-COB-24` | R53 | `R-ST-24` | R50 |
| `R-COB-25` | R54, R55 | `R-ST-25` | R02 |
| `R-COB-26` | R56 | `R-ST-26` | R01 |
| `R-COB-27` | R57 | `R-ST-27` | R54 |
| `R-COB-28` | R58 | `R-ST-28` | R55 |
| `R-COB-29` | R60 | `R-ST-29` | R56 |
| `R-COB-30` | R61 | `R-ST-30` | R57 |
| `R-COB-31` | R62 | `R-ST-31` | R58 |
| `R-COB-32` | R63 | `R-ST-32` | R59 |
| `R-COB-33` | R59 | `R-ST-33` | R60 |
| `R-COB-34` | R64 | `R-ST-34` | R61 |
| `R-COB-35` | R65 | `R-ST-35` | R62 |
| `R-COB-36` | R66 | `R-ST-36` | R63 |
| `R-COB-37` | R67 | `R-ST-37` | R74 |
| `R-COB-38` | R68, R69 | `R-ST-38` | R75 |
| `R-COB-39` | R70 | `R-ST-39` | R76 |
| `R-COB-40` | R71 | `R-ST-40` | R77 |
| `R-COB-41` | R72 | `R-ST-41` | R78 |
| `R-COB-42` | R73 | `R-ST-42` | R79 |
| `R-COB-43` | R78 | `R-ST-43` | R80 |
| `R-COB-44` | R80, R82 | `R-ST-44` | R82 |
| `R-COB-45` | R80, R82 | `R-ST-45` | R84 |
| `R-COB-46` | R79 | `R-ST-46` | R64 |
| `R-COB-47` | R83 | `R-ST-47` | R65 |
| `R-COB-48` | R84 | `R-ST-48` | R66 |
| — | — | `R-ST-49` | R67 |
| — | — | `R-ST-50` | R68 |
| — | — | `R-ST-51` | R69 |
| — | — | `R-ST-52` | R85 |
| — | — | `R-ST-53` | R86 |
| — | — | `R-ST-54` | R87 |
| — | — | `R-ST-55` | R88 |
| — | — | `R-ST-56` | R89 |
| — | — | `R-ST-57` | R90 |
| — | — | `R-ST-58` | R91 |
| — | — | `R-ST-59` | R92 |
| — | — | `R-ST-60` | R93 |
| — | — | `R-ST-61` | R94 |
| — | — | `R-ST-62` | R95 |
| — | — | `R-ST-63` | R96 |
| — | — | `R-ST-64` | R97 |
| — | — | `R-ST-65` | R83 |
| — | — | `R-ST-66` | R21 |
| — | — | `R-ST-67` | R22 |
| — | — | `R-ST-68` | R23 |
| — | — | `R-ST-69` | R24 |
| — | — | `R-ST-70` | R25 |
| — | — | `R-ST-71` | R26 |
| — | — | `R-ST-72` | R27 |
| — | — | `R-ST-73` | R28 |
| — | — | `R-ST-74` | R29 |
| — | — | `R-ST-75` | R30 |
| — | — | `R-ST-76` | R31 |
| — | — | `R-ST-77` | R32 |
| — | — | `R-ST-78` | R38 |
| — | — | `R-ST-79` | R39 |
| — | — | `R-ST-80` | R40 |
| — | — | `R-ST-81` | R41 |
| — | — | `R-ST-82` | R42 |
| — | — | `R-ST-83` | R43 |
| — | — | `R-ST-84` | R44 |
| — | — | `R-ST-85` | R45 |
| — | — | `R-ST-86` | R46 |
| — | — | `R-ST-87` | R47 |
| — | — | `R-ST-88` | R48 |
| — | — | `R-ST-89` | R81 |
| — | — | `R-ST-90` | R98 |
