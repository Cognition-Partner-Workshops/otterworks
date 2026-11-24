# Pharo quote screen — phase 2 table cross-check

Scope: all 65 Pharo entries from [phase 1](pharo-extract.md), extracted at `9c14702` from `demo-insrules` at `3d1c566`. No rating code, fixtures or tables changed.

**Score before cross-stack deduplication:** 65 rules checked, 25 missed entries found (R-ST-66–90), 90 found in total: **32 proven, 35 from-table, 10 amber, and 13 unproven**. The statuses are disjoint; 67 are proven or from-table. Five of the 40 shared data rows are unused (four stopped by validation or eligibility and one blocked by its effective dates). The 25 additions include 19 execution-backed table entries, five unused table entries, and one execution-backed endorsement condition.

Evidence comes from joining the original [policy fixtures](../fixtures/policies.dat) to the COBOL and headless Pharo outputs from `make insrules-reset` (`build/cobol.dat` and `build/pharo.txt`). Both stacks emitted 200 records: 190 OK, seven DEC and three REJ. The reset completed; its built-in comparison reported differences, and no modern parity work was undertaken. The Pharo batch calls the same `InsQuoteEngine>>quote:` as the screen. Amounts are cents unless the text says otherwise. COBOL prints the selected rate, factor and source; Pharo prints base and source, not the individual rate or factor. For Pharo the table keys, source and base together identify the winning row; intermediate calculations are reconstructed, not printed. Read COBOL totals from `OUT-TOTAL` in [RATEOUT.cpy](../cobol/copybooks/RATEOUT.cpy#L5-L16) (zero-based slice `[57:68]`); the current comparison reader's `[56:67]` slice omits the final digit. This cross-check does not change that reader.

Citation convention: the phase 1 heading supplies the `Class>>selector` and file lines; counterpart paragraphs and table lines are specified here or on the phase 1 entry. The [phase 1 Ask Devin search](https://partner-workshops.devinenterprise.com/search/api_4b8d3eac-b121-4be8-b34c-495c2b261971) did not source `demo-insrules`; its link returned no citation text here, and [DeepWiki](https://deepwiki.com/Cognition-Partner-Workshops/otterworks) returned HTTP 429. The citations below were verified in the branch source instead. No table citation is invented for a calculation that doesn't read a table.

## Method-group findings

Method names in this table are on `InsQuoteEngine` unless qualified. “No fixture reaches this” refers to the original policy corpus and shipped tables, not to what edited tables could do.

| Method group | IDs checked | Exclusivity, fallback, keys and row usage |
| --- | --- | --- |
| `quote:` | 01 | A failure stops later lookups and all charges. `P0000013` is REJ/LN, `P0000040` DEC/EX04, and `P0000001` OK with total 90650 in both. The rejected/declined records have zero base, fee and total. No direct table lookup here. |
| `validateLine:into:`, `validateExposure:into:` | 02–03 | Line rejection comes before exposure and table lookup. `P0000013` rejects WC despite [class row 16](../tables/class-factors.dat#L16) and [minimum row 8](../tables/minimum-premium.dat#L8); `P0000043` and `P0000044` use valid lines and reject negative and zero exposure, respectively. Validation has no alternate table row. |
| `checkEligibility:into:` | 04–10 | Match **line + class** before testing state. Exact state, `**`, and no row are mutually exclusive selections. `P0000040` (CA/7219/NY) = DEC/EX04 vs `P0000041` (same pair, IL) = OK with no row; `P0000042` (CA/7911/NY) = OK through the explicit Y rule. The latter's output proves the non-decline outcome, not an eligibility-row trace. `P0000005` and `P0000009` decline via wildcard EX01/EX02. All four [rows](../tables/line-eligibility.dat#L3-L6) are selected; no fixture reaches competing exact and wildcard rows because no line/class has both. |
| `lookupClassRate:into:` | 11–14 | Match **line + class + effective date**, not class by itself. `P0000001` (GL/91340) and `P0000006` (PR/0311) select rates 4.1500 and 0.3800. `P0000028`/ `P0000030` isolate the GL/41650 June 30/July 1 switch (79800/85500 base); those intervals do not overlap. No fixture reaches CL rejection or competing in-force rows. All 11 reachable rows are evidenced below or in R-ST-12/13. Rows 8, 12 and 16 are blocked upstream, not selected zero rates. No class code is shared across lines, so no fixture isolates the line predicate with a class-code collision. |
| `lookupTerritory:into:` | 15–19 | Match **line + territory + effective date**: `P0000015` GL/010 gets 0.950/T and `P0000020` PR/010 gets 0.900/T. Exact T wins; `P0000014` explicitly requests 000 and gets T, whereas `P0000018` requests missing 099 and gets D at the same factor. `P0000023` (expired PR/060) gets PR/000 at 1.000/D. No fixture reaches CA/000 as D (it is exercised as T), overlapping dated rows for the same key, or TR: every in-force allowed class is covered by an in-force 000 for its line. The only unused territory row is PR/060, line 12. |
| `lookupOverride:into:` | 20–24 | Match **line + class + requested territory + effective date**. An O overwrites T or D, not a second multiplier. `P0000031`/ `P0000032` produce 1.500/O and the same 139965 base despite different in-force GL/040 factors; `P0000017` (wrong class), `P0000033` (wrong territory), `P0000034` (before start) and `P0000038` (after end) keep T. `P0000100` (GL/91580/099) keeps D and does not get the 040 override. All three [rows](../tables/overrides.dat#L3-L5) fire; no fixture reaches O replacing D (each override's entire interval has an exact territory row), two competing overrides, or a cross-line same-class collision. |
| `InsRatingTables>>row:from:inForceOn:` | 25–26 | Both date bounds are inclusive; blank end uses sentinel 99999999 in both stacks. `P0000034`/ `P0000035` and `P0000037`/ `P0000038` show the dated override start/end transitions. `P0000128` uses open-end GL/41650 and GL/000 in September (286979/T). Eligibility and minimum have no date columns. |
| `basePremium:quote:`, `round:scale:` | 27–28 | The two rounding steps are sequential, not competing table rules. `P0000092` yields 45097 in both (one final rounding would yield 45098); `P0000065` yields 52773 from a half-cent factor step. Class/rate and territory/factor row choices are accounted for in their lookup groups. |
| `experienceMod:premium:` | 29–31 | The three-claim surcharge (`P0000047`: 108419), claims-free tenure credit (`P0000045`: 78062), and neutral fallback (`P0000046`: 86735) cannot stack; all share base 86735 and agree. No table. |
| `deductibleCredit:premium:` | 32–36 | GL bypass is separate (`P0000053`: unchanged with a 5000 deductible). On PR/CA only the highest eligible threshold is used (`P0000048`–`P0000052`: no credit or 2%, 5%, 8%). No table. |
| `applyMinimum:premium:quote:` | 37–43 | Match **line + state**; exact beats `**` rather than stacking. `P0000061`/ `P0000062` start at 44000 and floor to 75000/50000; `P0000026` uses CA/TX 120000, while `P0000121` (CA line in the state CA) uses CA/\*\* 100000 rather than GL/CA 75000. `P0000064` hits PR/\*\* 35000. `P0000001` is above its floor and remains 87150/N. No fixture reaches equality or the no-row fallback (all valid lines have a wildcard). Only WC/\*\* is unused. |
| `rate:into:` | 44–45 | Pharo and COBOL select the same floor rows but can apply the floor at different points; see amber findings. Formula stage outcomes are not independent table matches. COBOL's additional PR/FL wind lookup has no matching PR/WND row or Pharo step. |
| `scheduleMod:premium:` | 46–48 | Low clamp, in-range adjustment and high clamp are exclusive; `P0000054`/ `P0000055` give 54780, `P0000056` gives 83996 and `P0000057` gives 91300 from the same 73040 base in both. No table. |
| `multiPolicy:premium:` | 49–51 | Selected + GL/PR earns one 5% discount (`P0000058`, `P0000059`); selected CA (`P0000060`) and unselected GL/PR (`P0000001`, `P0000006`) are neutral in both. No table. |
| `endorsements:premium:`, `wholeDollars:` | 52–64 | Line guards make PR equipment mutually exclusive with GL additional insureds or hired/non-owned auto, and with GL/CA waiver. Eligible GL charges can combine (`P0000068`: 12500) but the full sum and capped result are alternative outcomes (`P0000073`: 12650 cap). `P0000070`/ `P0000071` evidence the PR floor vs percentage alternatives. No fixture reaches a negative GL additional-insured count, a positive non-GL count, selected PR waiver, or equipment exactly at the $75 crossover. `P0000073` has non-PR equipment selected, but the cap masks that guard in the output. No table. |
| `policyFee` | 65 | No alternative fee row: successful `P0000001` has 3500 fee in both; rejected `P0000013` has zero because the fee step is skipped. No table. |

## Missed entries

These are additions to the phase 1 list. Their status applies to the specified condition, not every use of that key.

### Class rate rows

Pharo: [`InsQuoteEngine>>lookupClassRate:into:`, 80–87](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L80-L87). COBOL: [`RATEPREM.cbl:2100-LOOKUP-CLASS`, 318–335](../cobol/RATEPREM.cbl#L318-L335). Pharo and COBOL base amounts agree on all proving fixtures below.

| ID | Statement | Table citation | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- | --- |
| R-ST-66 | Use a base rate of 4.1500 for GL/91340 from January 1, 2026. | `tables/class-factors.dat:3` | `P0000001`: base 87150. | from-table |
| R-ST-67 | Use a base rate of 6.2000 for GL/91580 from January 1, 2026. | `tables/class-factors.dat:4` | `P0000002`: base 130200. | from-table |
| R-ST-68 | Use a base rate of 1.1000 for GL/18501 from January 1, 2026. | `tables/class-factors.dat:7` | `P0000004`: base 23100. | from-table |
| R-ST-69 | The table lists a base rate of 9.7500 for GL/91111 from January 1, 2026, but eligibility preempts it. | `tables/class-factors.dat:8`; `tables/line-eligibility.dat:3` | No fixture reaches this rate row; `P0000005` declines EX01 before class lookup. | unproven |
| R-ST-70 | Use a base rate of 0.3800 for PR/0311 from January 1, 2026. | `tables/class-factors.dat:9` | `P0000006`: base 57000. | from-table |
| R-ST-71 | Use a base rate of 0.5200 for PR/0702 from January 1, 2026. | `tables/class-factors.dat:10` | `P0000007`: base 78000. | from-table |
| R-ST-72 | Use a base rate of 0.7100 for PR/0900 from January 1, 2026. | `tables/class-factors.dat:11` | `P0000008`: base 106500. | from-table |
| R-ST-73 | The table lists a base rate of 0.4400 for PR/0567 from January 1, 2026, but eligibility preempts it. | `tables/class-factors.dat:12`; `tables/line-eligibility.dat:4` | No fixture reaches this rate row; `P0000009` declines EX02 before class lookup. | unproven |
| R-ST-74 | Use a base rate of 610.0000 for CA/7398 from January 1, 2026. | `tables/class-factors.dat:13` | `P0000010`: base 183000. | from-table |
| R-ST-75 | Use a base rate of 1450.0000 for eligible CA/7219 from January 1, 2026. | `tables/class-factors.dat:14`; `tables/line-eligibility.dat:5` | `P0000041` (IL): base 435000; `P0000040` (NY) declines EX04 instead. | from-table |
| R-ST-76 | Use a base rate of 520.0000 for CA/7911 from January 1, 2026. | `tables/class-factors.dat:15` | `P0000012`: base 156000. | from-table |
| R-ST-77 | The table lists a base rate of 0.2500 for WC/8810 from January 1, 2026, but line validation preempts it. | `tables/class-factors.dat:16` | No fixture reaches this rate row; `P0000013` rejects LN before class lookup. | unproven |

### Territory factor rows

Pharo: [`InsQuoteEngine>>lookupTerritory:into:`, 90–104](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L90-L104). COBOL: [`RATEPREM.cbl:2200-LOOKUP-TERRITORY`, 338–365](../cobol/RATEPREM.cbl#L338-L365). All rows below start January 1, 2026 and have no end date unless specified; bases and T/D agree.

| ID | Statement | Table citation | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- | --- |
| R-ST-78 | Use factor 1.000 for GL/000, whether explicitly requested or selected as the GL fallback. | `tables/territory-factors.dat:3` | `P0000014`: 74700/T; `P0000018`: 74700/D. | from-table |
| R-ST-79 | Use factor 0.950 for GL/010. | `tables/territory-factors.dat:4` | `P0000015`: 70965/T. | from-table |
| R-ST-80 | Use factor 1.100 for GL/020. | `tables/territory-factors.dat:5` | `P0000016`: 82170/T. | from-table |
| R-ST-81 | Use factor 1.000 for PR/000, whether explicitly requested or selected as the PR fallback. | `tables/territory-factors.dat:8` | `P0000019`: 45600/T; `P0000023`: 45600/D. | from-table |
| R-ST-82 | Use factor 0.900 for PR/010. | `tables/territory-factors.dat:9` | `P0000020`: 41040/T. | from-table |
| R-ST-83 | Use factor 1.250 for PR/030 when there is no override. | `tables/territory-factors.dat:10` | `P0000021`: 57000/T. | from-table |
| R-ST-84 | Use factor 1.150 for PR/040. | `tables/territory-factors.dat:11` | `P0000022`: 52440/T. | from-table |
| R-ST-85 | The table lists PR/060 at 1.400 for January 1–December 31, 2025, but no in-force PR class overlaps that interval. | `tables/territory-factors.dat:12`; `tables/class-factors.dat:9–12` | No fixture reaches this factor; all PR class rows start in 2026, and `P0000023` takes 000/D instead. | unproven |
| R-ST-86 | Use factor 1.000 when CA/000 is explicitly requested. | `tables/territory-factors.dat:13` | `P0000024`: 122000/T. No fixture reaches the same row as fallback D. | from-table |
| R-ST-87 | Use factor 1.300 for CA/020 when there is no override. | `tables/territory-factors.dat:14` | `P0000025`: 158600/T. | from-table |
| R-ST-88 | Use factor 0.850 for CA/050. | `tables/territory-factors.dat:15` | `P0000026`: 103700/T. | from-table |

### Minimum and endorsement conditions

| ID | Statement | Source citations | Proving fixture and execution evidence | Status |
| --- | --- | --- | --- | --- |
| R-ST-89 | The table lists a $250 minimum for WC in all states, but line validation preempts it. | [`InsQuoteEngine>>applyMinimum:premium:quote:`, 147–157](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L147-L157); [`RATEPREM.cbl:3500-MINIMUM-PREMIUM`, 446–469](../cobol/RATEPREM.cbl#L446-L469); `tables/minimum-premium.dat:8`. | No fixture reaches this minimum; `P0000013` rejects LN with minimum N in both. | unproven |
| R-ST-90 | A GL quote with zero additional insureds and no selected optional endorsements adds no endorsement charge. | [`InsQuoteEngine>>endorsements:premium:`, 173–187](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L173-L187); no COBOL endorsement step, compare [`RATEPREM.cbl:3600-POLICY-FEE`, 471–473](../cobol/RATEPREM.cbl#L471-L473); no table. | `P0000001`: Pharo prints zero endorsements, and both totals are 90650 (87150 modified + 3500 fee). | proven |

## Corrections and amber findings for the merge

- **R-ST-19:** strengthen the reason from fixture-only to table-constrained: the class lookup runs first and the 000 row covers every in-force class date for each allowed line. Preserve `unproven`; no fixture reaches TR.
- **R-ST-56/57:** the $75 minimum also covers equality (both operands give the same amount); R-ST-56's example is below and R-ST-57's is above. No fixture reaches equality. No phase 1 status or proving fixture changed.
- **R-ST-44 (amber):** [Pharo `rate:into:`, 43–56](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L43-L56) floors before schedule/package; [COBOL `1000-RATE-POLICY`, 254–261](../cobol/RATEPREM.cbl#L254-L261) floors after them. The disagreement is order, not mismatched table keys. `P0000065` (GL, [minimum row 3](../tables/minimum-premium.dat#L3)) yields 40107/N vs 50000/Y; `P0000066` (PR, [row 5](../tables/minimum-premium.dat#L5)) yields 28263/Y vs 35000/Y; `P0000067` yields 60000/Y vs 55440/N.
- **R-ST-45, 52–53, 56–57, 59, 61, 63–64 (amber):** Pharo adds eligible endorsement charges and caps their sum, while COBOL has no endorsement step and computes only premium + fee. No shared table controls these charges. `P0000071` has modified premium 416000 in both, but Pharo adds 12500 endorsement plus 3500 fee (432000) whereas COBOL totals 419500; `P0000073` shows the cap (12650) and totals 66750 vs 54100. The same disagreement accounts for the other positive endorsement examples in phase 1.
- **COBOL-only wind path, not a new Pharo rule or a fixture-backed disagreement:** [`RATEPREM.cbl:3450-WIND-SURCHARGE`, 433–443](../cobol/RATEPREM.cbl#L433-L443) matches PR + FL, then looks for PR + WND. [The territory table](../tables/territory-factors.dat#L3-L15) has no WND row, so COBOL retains 1.000. [Pharo `rate:into:`](../smalltalk/src/InsRating/InsQuoteEngine.class.st#L43-L56) has no counterpart. `P0000101` (PR/FL) ends at 538315 modified and 541815 total in both; no fixture reaches a non-neutral factor.
