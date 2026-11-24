# COBOL shared-table cross-check

Source: `demo-insrules` at `3d1c5662441923c6361912e088f2f9c60ae6d6e9`. Rule IDs refer to [the COBOL extraction](cobol-rules.md). Policy IDs refer to `legacy-rating/fixtures/policies.dat`. Evidence is from `make insrules-reset`: COBOL `legacy-rating/build/cobol.dat` (decoded using `cobol/copybooks/RATEOUT.cpy`) and Pharo `legacy-rating/build/pharo.txt` (the batch invokes the same `InsQuoteEngine>>quote:` as the screen). Both read 200 policies (190 OK, 7 DEC, 3 REJ). Money below is in dollars; `T`, `D` and `O` are the executed factor-source codes. Rates and factors are printed by COBOL; Pharo's canonical output exposes base/modified amounts and the source code, not the raw rate or factor.

## Summary

| Measure | Total | With fixture | Without fixture |
| --- | ---: | ---: | ---: |
| Extracted rules checked | 48 | 44 | 4 |
| Exclusivity pairs (E) | 36 | 29 | 7 |
| Table fallbacks (F) | 9 | 6 | 3 |
| Paired/composite-key checks (K) | 9 | 5 | 4 |
| Physical data rows unused in the COBOL run (U) | 5 | 0 | 5 |

Of 40 table data rows, 35 were selected and 5 were not. A fixture that demonstrates *why* a row was skipped does not count as selecting that row. For an exclusivity pair, the witness column needs evidence for both alternatives; for precedence between overlapping table rows it needs a case where both rows are candidates. These checks are not extra rule IDs, and a fixture can demonstrate more than one check.

Status after cross-check: **29 proven, 12 from-table, 3 amber, 4 unproven**. One status change: **R-COB-43 amber → from-table** (same selected floor, different application order; retain the order difference under R-COB-44/45).

Smalltalk references below use files under `legacy-rating/smalltalk/src/InsRating/`: `InsQuoteEngine.class.st` for `InsQuoteEngine>>` and `InsRatingTables.class.st` for `InsRatingTables>>`. Groups without a lookup cite any relevant row as input context, not as the source of the rule.

## 0130-OPEN-END-DATE — R-COB-01

`RATEPREM.cbl:0130-OPEN-END-DATE` 223–229 (load calls 110–138, 172–186); `InsRatingTables>>row:from:inForceOn:` 46–53. Blank ends on the class, territory and override rows remain in force at the fixture date: `tables/class-factors.dat:3` and `tables/territory-factors.dat:4` give P0000015 rate 4.1500, factor 0.950/T and base $709.65; `tables/overrides.dat:4` gives P0000035 and P0000091 factor 1.600/O on March 1 and December 22. Dated-row alternatives and unused rows are counted at their lookup paragraphs below. This loader has no no-match lookup or composite key of its own.

## 1000-RATE-POLICY — R-COB-02

`RATEPREM.cbl:1000-RATE-POLICY` 231–262; `InsQuoteEngine>>quote:` 28–40. **E (1):** early exit vs rating: P0000013 stops with REJ/LN, P0000043 with REJ/EX, and P0000040 at `tables/line-eligibility.dat:5` with DEC/EX04 (each has zero base, modified amount, and total); P0000001 rates to $906.50 total. No direct table lookup, fallback, paired key, or unused row in the dispatcher.

## 1100-VALIDATE-LINE — R-COB-03/04

`RATEPREM.cbl:1100-VALIDATE-LINE` 276–281; `InsQuoteEngine>>validateLine:into:` 59–61. **E (1):** P0000001 (GL), P0000006 (PR) and P0000010 (CA) rate; P0000013 (WC) is REJ/LN even though `tables/class-factors.dat:16` and `tables/minimum-premium.dat:8` contain WC rows (counted unused in their lookup groups). No fallback or paired key.

## 1200-VALIDATE-EXPOSURE — R-COB-05

`RATEPREM.cbl:1200-VALIDATE-EXPOSURE` 283–287; `InsQuoteEngine>>validateExposure:into:` 64–66. **E (1):** P0000043 (negative) and P0000044 (zero) return REJ/EX; P0000006 (positive, `tables/class-factors.dat:9`) rates. No table lookup, fallback, paired key, or unused row.

## 2000-CHECK-ELIGIBILITY — R-COB-06–08

`RATEPREM.cbl:2000-CHECK-ELIGIBILITY` 291–310; `InsQuoteEngine>>checkEligibility:into:` 69–77.

- **E (3):** Exact vs wildcard: the source stops after the first exact state match, but no line/class has both an exact and wildcard row in `tables/line-eligibility.dat:3–6`; **no fixture reaches this** collision. Exact vs no row: P0000040 (NY) declines EX04 versus P0000041 (IL) rates, both CA/7219. Wildcard vs no row: P0000005 declines EX01 versus P0000041 rates.
- **F (2):** No exact state uses the same line/class's wildcard row: P0000005 and P0000009 decline EX01 and EX02 (`tables/line-eligibility.dat:3–4`). No exact or wildcard row leaves the policy eligible: P0000041 misses the NY-only row at line 5 and rates with COBOL class rate 1450.0000.
- **K (2):** The selector requires line + class + state (or same line/class + `**`). At fixed line CA, P0000040 (7219/NY) declines while P0000041 (7219/IL) and P0000042 (7911/NY) rate; lines 5 and 6 differentiate the rows. The separate wrong-line/same-class case cannot be isolated: the shipped classes do not recur across lines, and **no fixture reaches this** contrast.
- Unused: none; all four eligibility rows are reached (see next group).

## 2010-APPLY-ELIGIBILITY — R-COB-09/10

`RATEPREM.cbl:2010-APPLY-ELIGIBILITY` 312–316; `InsQuoteEngine>>checkEligibility:into:` 76. **E (1):** Selected `N` and non-`N` cannot both apply. `tables/line-eligibility.dat:3–5` yield EX01/EX02/EX04 for P0000005/P0000009/P0000040; P0000042 reaches the `Y` wildcard at line 6 and rates with $1,560.00 base. The table and input identify its selected `Y` row; OK alone does not distinguish it from no eligibility row. No separate fallback, key, or unused row.

## 2100-LOOKUP-CLASS — R-COB-11–14

`RATEPREM.cbl:2100-LOOKUP-CLASS` 318–335; `InsQuoteEngine>>lookupClassRate:into:` 80–87.

- **E (2):** `tables/class-factors.dat:5–6` cannot both be effective: P0000028 June 30 gives 2.1000/$798.00 base and P0000030 July 1 gives 2.2500/$855.00. Selected rate vs CL rejection: **no fixture reaches this** rejection.
- **F (1):** No in-force line/class row rejects CL without a default (e.g. the GL/41650 rows at lines 5–6 start on or after January 1, 2026); **no fixture reaches this**.
- **K (2):** Line + class + date are required; at fixed line GL, P0000001 (91340) and P0000003 (41650) select rates 4.1500 and 2.1000 (`tables/class-factors.dat:3,5`). No shipped class code occurs under a second line and **no fixture reaches this** wrong-line/same-class contrast.
- **U (3):** `tables/class-factors.dat:8,12`: GL/91111 and PR/0567 decline earlier for P0000005 and P0000009 respectively, as the wildcard `N` rows in `tables/line-eligibility.dat:3–4` prevent any rating of those keys. `tables/class-factors.dat:16`: P0000013 rejects WC at line validation. **no fixture reaches this** class lookup for any of the three rows; no policy can reach those rows with the shipped guards and tables.

## 2200-LOOKUP-TERRITORY — R-COB-15–19

`RATEPREM.cbl:2200-LOOKUP-TERRITORY` 338–365; `InsQuoteEngine>>lookupTerritory:into:` 90–104.

- **E (4):** Exact vs default: P0000014 explicitly requests 000 (1.000/T), whereas P0000018 falls back to the same row (1.000/D). Exact vs TR and default vs TR: **no fixture reaches this** rejection (two pairs). The two GL/040 effective windows exclude each other: P0000027 June 30 gives 1.200/T and P0000029 July 1 gives 1.350/T (`tables/territory-factors.dat:6–7`).
- **F (2):** Missing GL/099 (P0000018) and out-of-force PR/060 (P0000023) fall back to the same line's 000, 1.000/D (`tables/territory-factors.dat:3,8,12`). Missing both exact and in-force 000 rejects TR; the defaults at lines 3, 8 and 13 cover the fixture dates, so **no fixture reaches this**.
- **K (1):** Line + territory + date are required. P0000015 GL/010 gives 0.950/T and P0000020 PR/010 gives 0.900/T; changing GL to 020 (P0000016) gives 1.100/T (`tables/territory-factors.dat:4–5,9`).
- **U (1):** `tables/territory-factors.dat:12` (PR/060) is loaded but expires December 31, 2025. P0000023 requests 060 on March 15, 2026 but emits 1.000/D: **no fixture reaches this** row in force. A date in 2025 would also need an in-force PR class before the territory lookup; the shipped PR class rows all start January 1, 2026.

## 2300-LOOKUP-OVERRIDE — R-COB-20–24

`RATEPREM.cbl:2300-LOOKUP-OVERRIDE` 368–382; `InsQuoteEngine>>lookupOverride:into:` 107–117.

- **E (1):** A matching override replaces the selected territory factor (one output factor, O); without it the selected factor stays. P0000031 emits 1.500/O and $1,399.65 base, not 1.200/T or the stacked 1.800; P0000027 keeps 1.200/T for GL/040 with a different class (`tables/overrides.dat:3`, `tables/territory-factors.dat:6`).
- **F (1):** P0000033 keeps 1.100/T (wrong territory); P0000034 keeps 1.250/T (before start); P0000038 keeps 1.300/T (after end); P0000018 keeps 1.000/D with no override. All three shipped overrides are covered by the corresponding exact territories throughout their effective windows; **no fixture reaches this** D-to-O replacement.
- **K (2):** At fixed line GL and in-force date, P0000031 (91580/040, 1.500/O), P0000033 (91580/020, 1.100/T), and P0000027 (91340/040, 1.200/T) distinguish class and original territory (`tables/overrides.dat:3`, `tables/territory-factors.dat:5–6`). The line is independently required by source, but **no fixture reaches this** wrong-line/same-class contrast.
- Unused: none. P0000031, P0000035, and P0000037 select `tables/overrides.dat:3–5`, respectively (1.500/O, 1.600/O, 1.550/O).

## 3000-BASE-PREMIUM — R-COB-25

`RATEPREM.cbl:3000-BASE-PREMIUM` 384–387; `InsQuoteEngine>>basePremium:quote:` 120–124. P0000092 uses `tables/class-factors.dat:10` and `tables/territory-factors.dat:11`: 754.14 × 0.5200 rounds to $392.15, then × 1.150 gives $450.97 in both stacks; one rounding would give $450.98. No alternative branches, fallback, paired key, or unused row; the selected inputs feed this calculation.

## 3100-EXPERIENCE-MOD — R-COB-26–28

`RATEPREM.cbl:3100-EXPERIENCE-MOD` 389–398; `InsQuoteEngine>>experienceMod:premium:` 127–133. **E (3):** The debit, credit and unchanged outcomes exclude each other pairwise. From the same $867.35 base (`tables/class-factors.dat:3`, `tables/territory-factors.dat:4`), P0000047 yields $1,084.19 (3 claims), P0000045 yields $780.62 (0 claims, 3 years) and P0000046 stays $867.35 (0 claims, 2 years). The last is the code's neutral branch, not a table fallback. No table key or unused row.

## 3200-DEDUCTIBLE-CREDIT — R-COB-29–33

`RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT` 401–413; `InsQuoteEngine>>deductibleCredit:premium:` 136–144. **E (10):** Each pair among the five outcomes excludes the other: PR thresholds $5,000/$2,500/$1,000/$999 (P0000051/50/49/48) yield $529.09/$546.35/$563.60/$575.10 from $575.10 base (`tables/class-factors.dat:11`, `tables/territory-factors.dat:9`); GL at $5,000 (P0000053) keeps $726.00. P0000052 gives CA's 8% credit, $1,555.50 → $1,431.06. The $999 and non-PR/CA paths leave the factor at 1.00; the thresholds are code, not table lookups, so there is no table fallback, paired key, or unused row.

## 3300-SCHEDULE-MOD — R-COB-34–36

`RATEPREM.cbl:3300-SCHEDULE-MOD` 415–423; `InsQuoteEngine>>scheduleMod:premium:` 160–164. **E (3):** Low clamp, high clamp and in-range are mutually exclusive pairwise. P0000054 (−30%) gives $547.80, P0000057 (+40%) gives $913.00, and P0000056 (+15%) gives $839.96, each from $730.40 using `tables/class-factors.dat:3` and `tables/territory-factors.dat:5`. P0000055 (−25%) gives $547.80 without clamping: it is an in-range witness, not a clamp witness. No table fallback, paired key, or unused row.

## 3400-MULTI-POLICY — R-COB-37/38

`RATEPREM.cbl:3400-MULTI-POLICY` 425–429; `InsQuoteEngine>>multiPolicy:premium:` 167–170. **E (1):** GL or PR with Y vs otherwise: P0000058 gives $880.00 → $836.00 (`tables/class-factors.dat:7`); P0000059 gives $760.00 → $722.00; P0000060 (CA/Y) and P0000001 (GL/N) stay at $1,560.00 and $871.50. No table fallback, paired key, or unused row.

## 3450-WIND-SURCHARGE — R-COB-39/40

`RATEPREM.cbl:3450-WIND-SURCHARGE` 433–443; `InsQuoteEngine>>rate:into:` 43–56 has no wind step; `InsQuoteEngine>>lookupTerritory:into:` 90–104 only looks up the requested territory or 000 by date. `tables/territory-factors.dat:8–12` contains all PR rows, none with WND.

- **E (1), K (1):** A Florida PR policy with an actual PR/WND row takes the last matching line + special territory row, ignoring dates; the neutral fallback applies if no row exists. **no fixture reaches this** selected-row outcome. Other lines or states bypass the lookup entirely; that guard has no observable premium contrast while the WND row is absent.
- **F (1):** P0000101 (PR/FL) emits $4,306.52 base and $5,383.15 modified, the 25% experience debit alone. The batch leaves the wind multiplier at 1.000, so the missing wind lookup does not create a disagreement on this fixture.
- Unused: no physical PR/WND row to count; the expired PR/060 row is counted under territory lookup.

## 3500-MINIMUM-PREMIUM — R-COB-41–46

`RATEPREM.cbl:3500-MINIMUM-PREMIUM` 446–469, and `RATEPREM.cbl:1000-RATE-POLICY` 254–261 for ordering; `InsQuoteEngine>>applyMinimum:premium:quote:` 147–157 and `InsQuoteEngine>>rate:into:` 43–56.

- **E (4):** Exact vs wildcard: `tables/minimum-premium.dat:3–4` both qualify on line for P0000061 (GL/CA) but the exact $750.00/Y wins; P0000062 (GL/IL) selects $500.00/Y. Exact vs no row and wildcard vs no row: **no fixture reaches this** no-row outcome (two pairs). Below vs at/above the selected amount: P0000062 floors to $500.00/Y and P0000001 stays $871.50/N; P0000067 demonstrates the differing order (batch $554.40/N, quote $600.00/Y).
- **F (2):** State miss falls back to the line's wildcard: P0000062 gets GL $500.00, P0000070 PR $350.00 and P0000082 CA $1,000.00 in batch (`tables/minimum-premium.dat:3,5–6`). With neither row the premium stays unchanged and the flag remains N; **no fixture reaches this** because all lines accepted by validation have wildcard rows.
- **K (1):** Line + state selects the floor: at fixed line GL, P0000061 (CA) / P0000062 (IL) select $750.00 / $500.00. At fixed state CA, P0000061 (line GL) takes row 4 but P0000082 (line CA) takes CA's $1,000.00 wildcard instead. P0000063 (line CA, state TX) gets that line's exact $1,200.00 rather than its wildcard (`tables/minimum-premium.dat:3–4,6–7`).
- **U (1):** `tables/minimum-premium.dat:8` (WC/**) is unreachable since P0000013 rejects WC, and **no fixture reaches this** floor.
- **R-COB-43 is from-table:** P0000082 has base $610.00, a 25% claims debit, a 2% deductible credit, and +25% schedule. In both paths $610.00 × 1.25 × 0.98 = $747.25 before schedule. COBOL applies schedule ($934.06) then floors to $1,000.00/Y. Pharo floors first to the same $1,000.00, then applies schedule to produce $1,250.00/Y. The selected row agrees; R-COB-44/45 retain the downstream amber ordering difference.

## 3600-POLICY-FEE — R-COB-47/48

`RATEPREM.cbl:3600-POLICY-FEE` 471–473 (constant line 75); `InsQuoteEngine>>policyFee` 195, `InsQuoteEngine>>rate:into:` 43–56 and `InsQuoteEngine>>endorsements:premium:` 173–187. P0000015 adds $35.00 to $709.65 on both stacks (input context `tables/class-factors.dat:3`), but P0000068/P0000069 give batch total $1,280.00 both times versus quote totals $1,405.00/$1,550.00 with nonzero endorsements. R-COB-48 remains amber. No fee table, branch pair, fallback, paired key, or unused row.

## Physical row coverage

`line → policy` below means one witness for selecting that row; the quoted class/territory amounts and reasons in the groups above come from the executed outputs. For a minimum row the witness actually floors; for territory rows these examples retain T or D to the output (not hidden by an override).

| Table | Data rows selected (line → policy ID) | Unused lines |
| --- | --- | --- |
| `tables/class-factors.dat` | 3 → P0000001; 4 → P0000002; 5 → P0000028; 6 → P0000030; 7 → P0000004; 9 → P0000006; 10 → P0000007; 11 → P0000008; 13 → P0000010; 14 → P0000011; 15 → P0000012 | 8, 12, 16 |
| `tables/line-eligibility.dat` | 3 → P0000005; 4 → P0000009; 5 → P0000040; 6 → P0000042 | — |
| `tables/territory-factors.dat` | 3 → P0000014; 4 → P0000015; 5 → P0000016; 6 → P0000027; 7 → P0000029; 8 → P0000019; 9 → P0000020; 10 → P0000021; 11 → P0000022; 13 → P0000024; 14 → P0000025; 15 → P0000026 | 12 |
| `tables/overrides.dat` | 3 → P0000031; 4 → P0000035; 5 → P0000037 | — |
| `tables/minimum-premium.dat` | 3 → P0000062; 4 → P0000061; 5 → P0000070; 6 → P0000082; 7 → P0000063 | 8 |
