# Golden rating rules

Run `INSR_20261124` · baseline `1b421600` · 200 golden policy fixtures.

Each row links to its [source citations](citations.md). Statuses are mutually exclusive: **proven** is shared behavior distinguished by an executed policy; **from-table** is a table-backed rule demonstrated by both legacy outputs; **amber** is an unresolved legacy difference; **unproven** means the available output does not distinguish the rule. See [score and replay notes](score.md).

## Validation and underwriting

| Rule | Statement | Executed witness or coverage limit | Status |
| --- | --- | --- | --- |
| [R01](citations.md#r01) | Both stacks reject a policy outside GL, PR and CA with reason LN. | P0000013: WC, REJ/LN. | proven |
| [R02](citations.md#r02) | Both stacks reject zero or negative exposure on a supported line with reason EX. | P0000043: −125.00, REJ/EX; P0000044: 0.00, REJ/EX. | proven |
| [R03](citations.md#r03) | The first failed check in line, exposure, eligibility, class and territory order stops the later checks and premium calculations. | P0000005: DEC/EX01 with zero base rate; P0000013: REJ/LN despite the WC class row. No fixture reaches competing simultaneous failures. | unproven |
| [R04](citations.md#r04) | A reject or decline carries no fee or total and does not set the minimum flag. | P0000005 and P0000013: fee and total 0.00, minimum flag N. | proven |
| [R05](citations.md#r05) | An exact-state eligibility match requires the policy line, class and state together. | P0000040: CA/7219 in NY → DEC/EX04; P0000041: same line/class in IL → OK. | from-table |
| [R06](citations.md#r06) | If no exact-state eligibility row matches, both stacks use the same line and class with state `**` when such a row exists. | P0000005: GL/91111 IL → DEC/EX01; P0000042: CA/7911 NY → OK. | from-table |
| [R07](citations.md#r07) | With no line/class/state or line/class/`**` eligibility row, the policy passes the eligibility check. | P0000041: CA/7219 IL → OK. | from-table |
| [R08](citations.md#r08) | A matching eligibility row coded N declines the policy with that row's reason. | P0000005, P0000009, P0000040: DEC with EX01, EX02, EX04 respectively. | from-table |
| [R09](citations.md#r09) | A matching eligibility row not coded N leaves the policy eligible for further checks. | P0000042 matches the Y row and rates OK; ordinary output does not distinguish explicit allowance from no match. | unproven |

## Rate selection and base premium

| Rule | Statement | Executed witness or coverage limit | Status |
| --- | --- | --- | --- |
| [R10](citations.md#r10) | The base rate comes from an in-force row matching the policy line and class. | P0000028 on 2026-06-30: 2.1000; P0000030 on 2026-07-01: 2.2500. | from-table |
| [R11](citations.md#r11) | Without an in-force line/class row, the policy is rejected with reason CL. | No fixture reaches this. | unproven |
| [R12](citations.md#r12) | Both stacks first use an in-force factor matching line and requested territory on the effective date, including both endpoints, and record source T. | P0000027 on 2026-06-30: 1.200/T; P0000029 on 2026-07-01: 1.350/T; P0000014 explicitly requests 000 and also returns T. | from-table |
| [R13](citations.md#r13) | When the requested territory is missing or out of force, both stacks use an in-force territory 000 row for the same line and record source D. | P0000018: unknown GL/099 → 1.000/D; P0000023: expired PR/060 → 1.000/D. | from-table |
| [R14](citations.md#r14) | If neither an exact nor a default territory row is in force, the policy is rejected with reason TR before override lookup. | No fixture reaches this; the current supported lines each have a default territory throughout the dates for which class rates are available. | unproven |
| [R15](citations.md#r15) | An in-force override matching line, class and the original requested territory replaces rather than multiplies the selected territory factor and records source O. | P0000031: GL/91580/040 → 1.500/O, not 1.800; P0000027: same line/territory but different class → 1.200/T; P0000033: same line/class but different territory → 1.100/T. No fixture reaches an override after a territory fallback. | from-table |
| [R16](citations.md#r16) | When no override matches all keys and the inclusive date window, both stacks leave the territory factor and its source unchanged. | P0000034/P0000038 retain T outside the override dates; P0000023 retains D. | from-table |
| [R17](citations.md#r17) | A blank end date keeps a class, territory or override row open after its start date. | P0000030 and P0000029 select the open class and territory rows; P0000091 selects the open override after its start date. | from-table |
| [R18](citations.md#r18) | Both stacks multiply exposure by the base rate, round to cents, then multiply by the selected territory factor and round the base premium to cents again. | P0000092: 754.14 × 0.5200 → 392.15; × 1.150 → base 450.97, not 450.98 from one rounding at the end. | proven |

## Premium adjustments

| Rule | Statement | Executed witness or coverage limit | Status |
| --- | --- | --- | --- |
| [R19](citations.md#r19) | Three or more claims in three years increase premium by 25%. | P0000047: 3 claims, 867.35 → 1,084.19. | proven |
| [R20](citations.md#r20) | Zero claims and at least three years in business reduce premium by 10%. | P0000045: zero claims, 3 years, 867.35 → 780.62. | proven |
| [R21](citations.md#r21) | Other claim and years-in-business combinations do not change premium. | P0000046: zero claims, 2 years, stays 867.35; P0000001: one claim, stays 871.50. | proven |
| [R22](citations.md#r22) | Property and commercial auto get an 8% credit for deductibles of 5,000 or more. | P0000051 (PR): 575.10 → 529.09; P0000052 (CA): 1,555.50 → 1,431.06. | proven |
| [R23](citations.md#r23) | Property and commercial auto get a 5% credit for deductibles of 2,500 through 4,999. | P0000050: 575.10 → 546.35 with deductible 2,500. | proven |
| [R24](citations.md#r24) | Property and commercial auto get a 2% credit for deductibles of 1,000 through 2,499. | P0000049: 575.10 → 563.60 with deductible 1,000. | proven |
| [R25](citations.md#r25) | Property and commercial auto get no credit for deductibles below 1,000. | P0000048: 575.10 unchanged with deductible 999. | proven |
| [R26](citations.md#r26) | General liability receives no deductible credit. | P0000053: GL, deductible 5,000, stays 726.00. | proven |
| [R27](citations.md#r27) | A schedule adjustment below −25% is applied as −25%. | P0000054: −30%, 730.40 → 547.80, same as P0000055 at −25%. | proven |
| [R28](citations.md#r28) | A schedule adjustment above +25% is applied as +25%. | P0000057: +40%, 730.40 → 913.00. | proven |
| [R29](citations.md#r29) | A schedule adjustment between −25% and +25% inclusive is applied as entered. | P0000055: −25% → 547.80; P0000056: +15% → 839.96, both on 730.40. | proven |
| [R30](citations.md#r30) | General liability and property get a 5% discount when the multi-policy flag is Y. | P0000058 (GL): 880.00 → 836.00; P0000059 (PR): 760.00 → 722.00. | proven |
| [R31](citations.md#r31) | General liability and property get no multi-policy discount without a Y flag. | P0000001 (GL) with N: stays 871.50; P0000006 (PR) with N: stays 570.00. | proven |
| [R32](citations.md#r32) | Commercial auto does not receive a multi-policy discount even with a Y flag. | P0000060: CA with Y stays 1,560.00. | proven |

## Florida property wind

| Rule | Statement | Executed witness or coverage limit | Status |
| --- | --- | --- | --- |
| [R33](citations.md#r33) | For Florida property with a PR/WND row, the batch applies the last matching wind factor without checking its effective dates, but the quote screen has no wind step. | No fixture reaches a PR/WND row; P0000148 shows a neutral result with the checked-in table. This is a source-level difference, not an observed golden mismatch. | amber |
| [R34](citations.md#r34) | For Florida property without a PR/WND row, the wind multiplier is 1.000 and does not change premium. | P0000148: both show base and modified $3,665.87; output cannot distinguish the COBOL 1.000 multiplier from Pharo skipping the step. | unproven |
| [R35](citations.md#r35) | The wind adjustment is skipped for non-Florida property and for lines other than property. | P0000006 (PR/IL) and P0000001 (GL/IL) are outside the gate; with no WND row, no fixture distinguishes COBOL skipping the multiplier. | unproven |

## Minimum, fee and endorsements

| Rule | Statement | Executed witness or coverage limit | Status |
| --- | --- | --- | --- |
| [R36](citations.md#r36) | A line/state minimum takes precedence over that line's all-states minimum. | P0000061 GL/CA: 440.00 → 750.00/Y vs P0000062 GL/IL: 440.00 → 500.00/Y; P0000063 CA/TX: 884.00 → 1,200.00/Y. | from-table |
| [R37](citations.md#r37) | If no exact line/state minimum exists, both stacks use the same line’s all-states minimum when one exists. | P0000062 GL/IL → $500.00/Y; P0000064 PR/FL → $350.00/Y; P0000121 CA without a state-specific row → $1,000.00/Y, all in both stacks. | from-table |
| [R38](citations.md#r38) | If neither an exact nor an all-states minimum matches, premium passes through without a minimum increase. | No fixture reaches this; each supported line has an all-states row. | unproven |
| [R39](citations.md#r39) | An amount strictly below the selected minimum is raised to that minimum and the minimum flag is set. | P0000062: $440.00 base → $500.00 modified / Y in both stacks; see R94 for the disagreeing timing. | from-table |
| [R40](citations.md#r40) | An amount above the selected minimum is not raised and the minimum flag stays off. | P0000001: $871.50 base and modified / N in both stacks. | from-table |
| [R41](citations.md#r41) | A successfully rated policy incurs a flat $35.00 fee. | P0000001: $35.00 fee in both stacks; each shows $906.50 total. | proven |
| [R42](citations.md#r42) | For one to three additional insureds on GL, the quote screen adds $50 per insured before the combined cap, but the batch adds nothing. | P0000076: one insured, Pharo endorsement $50.00; COBOL total equals modified plus fee. | amber |
| [R43](citations.md#r43) | For selected PR equipment breakdown when 3% of modified premium exceeds $75, the quote screen charges that percentage rounded to dollars before the combined cap, but the batch adds nothing. | P0000071: both modified $4,160.00; Pharo endorsement $125.00, COBOL adds none. | amber |
| [R44](citations.md#r44) | For selected GL or CA waiver of subrogation, the quote screen charges 2% of modified premium rounded to dollars before the combined cap, but the batch adds nothing. | P0000068 (GL): Pharo $100.00 for insureds plus $25.00 waiver; P0000072 (CA): Pharo $61.00 waiver; COBOL adds neither. | amber |
| [R45](citations.md#r45) | For selected GL hired and non-owned auto, the quote screen charges $120 before the combined cap, but the batch adds nothing. | P0000069: Pharo $120.00 HNOA plus $150.00 for insureds; COBOL adds neither. | amber |
| [R46](citations.md#r46) | Above the minimum, both stacks apply and round experience, deductible, schedule and multi-policy adjustments in that order. | P0000089: $1,950.10 × 0.90 × 0.92 × 1.05 × 0.95 yields $1,610.64 in both, not $1,610.65 with a single final rounding. | proven |

## Class-factor rows

| Rule | Statement | Executed witness or coverage limit | Status |
| --- | --- | --- | --- |
| [R47](citations.md#r47) | GL class 91340 has base rate 4.1500 from 2026-01-01. | P0000001: 4.1500. P0000001 produces $871.50 base / T in both stacks. | from-table |
| [R48](citations.md#r48) | GL class 91580 has base rate 6.2000 from 2026-01-01. | P0000002: 6.2000. P0000002 produces $1,302.00 base / T in both stacks. | from-table |
| [R49](citations.md#r49) | GL class 41650 has base rate 2.1000 from 2026-01-01 through 2026-06-30. | P0000028: 2.1000 on 2026-06-30. P0000028 produces $798.00 base / T in both stacks. | from-table |
| [R50](citations.md#r50) | GL class 41650 has base rate 2.2500 from 2026-07-01. | P0000030: 2.2500 on 2026-07-01. P0000030 produces $855.00 base / T in both stacks. | from-table |
| [R51](citations.md#r51) | GL class 18501 has base rate 1.1000 from 2026-01-01. | P0000004: 1.1000. P0000004 produces $231.00 base / T in both stacks. | from-table |
| [R52](citations.md#r52) | The table lists GL class 91111 at 9.7500 from 2026-01-01, but the all-states eligibility decline prevents using that rate. | P0000005: DEC/EX01; no fixture reaches this class-rate row. | unproven |
| [R53](citations.md#r53) | PR class 0311 has base rate 0.3800 from 2026-01-01. | P0000006: 0.3800. P0000006 produces $570.00 base / T in both stacks. | from-table |
| [R54](citations.md#r54) | PR class 0702 has base rate 0.5200 from 2026-01-01. | P0000007: 0.5200. P0000007 produces $780.00 base / T in both stacks. | from-table |
| [R55](citations.md#r55) | PR class 0900 has base rate 0.7100 from 2026-01-01. | P0000008: 0.7100. P0000008 produces $1,065.00 base / T in both stacks. | from-table |
| [R56](citations.md#r56) | The table lists PR class 0567 at 0.4400 from 2026-01-01, but the all-states eligibility decline prevents using that rate. | P0000009: DEC/EX02; no fixture reaches this class-rate row. | unproven |
| [R57](citations.md#r57) | CA class 7398 has base rate 610.0000 from 2026-01-01. | P0000010: 610.0000. P0000010 produces $1,830.00 base / T in both stacks. | from-table |
| [R58](citations.md#r58) | CA class 7219 has base rate 1,450.0000 from 2026-01-01 where eligible. | P0000011: 1,450.0000. P0000011 produces $4,350.00 base / T in both stacks. | from-table |
| [R59](citations.md#r59) | CA class 7911 has base rate 520.0000 from 2026-01-01. | P0000012: 520.0000. P0000012 produces $1,560.00 base / T in both stacks. | from-table |
| [R60](citations.md#r60) | The table lists WC class 8810 at 0.2500 from 2026-01-01, but both stacks reject WC before it looks for a class rate. | P0000013: REJ/LN; no fixture reaches this class-rate row. | unproven |
| [R105](citations.md#r105) | The table lists GL class 18501 at 1.1500 from 2027-01-01 with no end date. | No golden fixture reaches this row. The latest GL/18501 fixture is P0000093, effective 2026-12-19. | unproven |

**R51 catalog/table contradiction:** R51 describes 1.1000 from 2026-01-01 without an end date. The revised table ends the 1.1000 row on 2026-12-31 and starts the 1.1500 row the next day; the rows are mutually exclusive. R51 and the table are left unchanged by the catalog refresh. P0000004 still proves 1.1000 for its 2026 effective date, not an open-ended rate.

## Eligibility rows

| Rule | Statement | Executed witness or coverage limit | Status |
| --- | --- | --- | --- |
| [R61](citations.md#r61) | GL class 91111 is declined in every state with reason EX01. | P0000005: DEC/EX01. | from-table |
| [R62](citations.md#r62) | PR class 0567 is declined in every state with reason EX02. | P0000009: DEC/EX02. | from-table |
| [R63](citations.md#r63) | CA class 7219 is declined in NY with reason EX04. | P0000040: DEC/EX04; P0000041 in IL is OK. | from-table |
| [R64](citations.md#r64) | CA class 7911 has an all-states eligibility allowance. | P0000042 matches the Y row and is OK; OK alone cannot distinguish explicit allowance from no row. | unproven |

## Territory-factor rows

| Rule | Statement | Executed witness or coverage limit | Status |
| --- | --- | --- | --- |
| [R65](citations.md#r65) | GL territory 000 has a factor of 1.000 from 2026-01-01. | P0000014: 1.000/T; P0000018 defaults to 1.000/D. P0000014 produces $747.00 base / T in both stacks. | from-table |
| [R66](citations.md#r66) | GL territory 010 has a factor of 0.950 from 2026-01-01. | P0000015: 0.950/T. P0000015 produces $709.65 base / T in both stacks. | from-table |
| [R67](citations.md#r67) | GL territory 020 has a factor of 1.100 from 2026-01-01. | P0000016: 1.100/T. P0000016 produces $821.70 base / T in both stacks. | from-table |
| [R68](citations.md#r68) | GL territory 040 has a factor of 1.200 from 2026-01-01 through 2026-06-30 when not overridden. | P0000027: 1.200/T on 2026-06-30. P0000027 produces $1,494.00 base / T in both stacks. | from-table |
| [R69](citations.md#r69) | GL territory 040 has a factor of 1.350 from 2026-07-01 when not overridden. | P0000029: 1.350/T on 2026-07-01. P0000029 produces $1,680.75 base / T in both stacks. | from-table |
| [R70](citations.md#r70) | PR territory 000 has a factor of 1.000 from 2026-01-01. | P0000019: 1.000/T; P0000023 defaults to 1.000/D. P0000019 produces $456.00 base / T in both stacks. | from-table |
| [R71](citations.md#r71) | PR territory 010 has a factor of 0.900 from 2026-01-01. | P0000020: 0.900/T. P0000020 produces $410.40 base / T in both stacks. | from-table |
| [R72](citations.md#r72) | PR territory 030 has a factor of 1.250 from 2026-01-01 when not overridden. | P0000021: 1.250/T. P0000021 produces $570.00 base / T in both stacks. | from-table |
| [R73](citations.md#r73) | PR territory 040 has a factor of 1.150 from 2026-01-01. | P0000022: 1.150/T. P0000022 produces $524.40 base / T in both stacks. | from-table |
| [R74](citations.md#r74) | The PR territory 060 factor of 1.400 only applies from 2025-01-01 through 2025-12-31, before any property class rate is in force in the current table. | P0000023 is after expiration and uses 1.000/D; no fixture reaches the 1.400 factor. | unproven |
| [R75](citations.md#r75) | CA territory 000 has a factor of 1.000 from 2026-01-01. | P0000024: 1.000/T; no fixture reaches the CA default path. P0000024 produces $1,220.00 base / T in both stacks. | from-table |
| [R76](citations.md#r76) | CA territory 020 has a factor of 1.300 from 2026-01-01 when not overridden. | P0000025: 1.300/T. P0000025 produces $1,586.00 base / T in both stacks. | from-table |
| [R77](citations.md#r77) | CA territory 050 has a factor of 0.850 from 2026-01-01. | P0000026: 0.850/T. P0000026 produces $1,037.00 base / T in both stacks. | from-table |

## Minimum rows

| Rule | Statement | Executed witness or coverage limit | Status |
| --- | --- | --- | --- |
| [R78](citations.md#r78) | GL has a 500.00 all-states minimum when there is no state-specific row. | P0000062: 500.00/Y. | from-table |
| [R79](citations.md#r79) | GL in CA has a 750.00 minimum. | P0000061: 750.00/Y. | from-table |
| [R80](citations.md#r80) | PR has a 350.00 all-states minimum. | P0000064: 350.00/Y. | from-table |
| [R81](citations.md#r81) | CA has a 1,000.00 all-states minimum when there is no state-specific row. | P0000121: $1,000.00/Y in both; P0000082 also selects this row but the ordering difference changes the final modified premium (R94). | from-table |
| [R82](citations.md#r82) | CA in TX has a 1,200.00 minimum. | P0000063: 1,200.00/Y. | from-table |
| [R83](citations.md#r83) | The table lists a 250.00 minimum for WC, but both stacks reject WC before the minimum check. | P0000013: REJ/LN; no fixture reaches this minimum row. | unproven |

## Override rows

| Rule | Statement | Executed witness or coverage limit | Status |
| --- | --- | --- | --- |
| [R84](citations.md#r84) | GL class 91580 in territory 040 has a replacement factor of 1.500 from 2026-01-01 through 2026-12-31. | P0000031 and P0000032: 1.500/O; P0000032 is on the end date. P0000031 produces $1,399.65 base / O in both stacks. | from-table |
| [R85](citations.md#r85) | PR class 0702 in territory 030 has a replacement factor of 1.600 from 2026-03-01. | P0000035: 1.600/O on the start date; P0000034: 1.250/T the previous day. P0000035 produces $3,411.20 base / O in both stacks. | from-table |
| [R86](citations.md#r86) | CA class 7219 in territory 020 has a replacement factor of 1.550 from 2026-01-01 through 2026-09-30 where eligible. | P0000037: 1.550/O on the end date; P0000038: 1.300/T the next day. P0000037 produces $8,990.00 base / O in both stacks. | from-table |

## Lookup and rounding boundaries

| Rule | Statement | Executed witness or coverage limit | Status |
| --- | --- | --- | --- |
| [R87](citations.md#r87) | When both a matching state and an all-states eligibility row exist, the state row wins. | No fixture reaches this; the loaded table has no such pair. | unproven |
| [R88](citations.md#r88) | When rows tie on keys, dates and precedence, the first matching data row in file order wins. | No fixture reaches this; there are no same-priority ties. The absent COBOL wind lookup (R33) is not first-match. | unproven |
| [R89](citations.md#r89) | Dated class, territory and override rows include the start and end dates. | P0000027/P0000028 match on the June 30 end; P0000029/P0000030 match on the July 1 start; P0000034/P0000035 bracket the PR override start; P0000037/P0000038 bracket the CA override end. | from-table |
| [R90](citations.md#r90) | For nonnegative premium calculations, an exact half-cent rounds up. | P0000065: the factor step gives $527.725, and both output $527.73 base. | proven |
| [R91](citations.md#r91) | Experience is applied and rounded before any deductible credit. | P0000097: $9,560.56 modified in both, distinguishing the reversed rounding order. | proven |
| [R92](citations.md#r92) | The schedule-adjusted amount is rounded before applying any multi-policy credit. | P0000076: $4,318.44 modified in both instead of $4,318.45 with reversed rounding order. | proven |
| [R93](citations.md#r93) | When the premium entering the minimum step exactly equals the selected minimum, the minimum flag remains off. | No fixture reaches exact equality at the minimum step. | unproven |

## Minimum timing and quote-only charges

| Rule | Statement | Executed witness or coverage limit | Status |
| --- | --- | --- | --- |
| [R94](citations.md#r94) | COBOL applies the minimum after schedule, multi-policy and wind, whereas Pharo applies it immediately after experience and deductible. | P0000065, P0000066, P0000067, P0000082 and P0000200; both outcomes are below. | amber |
| [R95](citations.md#r95) | For selected PR equipment breakdown when 3% of modified premium is at most $75, the quote screen uses $75 before the combined cap, but the batch adds nothing. | P0000070: modified $350.00 and Pharo endorsement $75.00 rather than $10.50; COBOL adds none. | amber |
| [R96](citations.md#r96) | For more than three additional insureds on GL, the quote screen uses three before the combined cap, but the batch adds nothing. | P0000069: five insureds plus HNOA yield $150.00 + $120.00 in Pharo; COBOL adds neither. | amber |
| [R97](citations.md#r97) | Negative additional-insured counts are treated as zero on GL quotes. | No fixture reaches a negative additional-insured count. | unproven |
| [R98](citations.md#r98) | Percentage-based charges are rounded to cents and then to whole dollars before being added. | P0000071: $124.80 becomes $125.00 in Pharo; P0000068: $24.90 waiver becomes $25.00; COBOL adds neither. These distinguish whole-dollar rounding, not a half-dollar tie. | amber |
| [R99](citations.md#r99) | The sum of applicable endorsements is capped at 25% of the modified premium rounded to cents. | P0000073: Pharo charges $126.50 on $506.00 modified rather than the $280.00 uncapped sum; COBOL adds none. | amber |
| [R100](citations.md#r100) | The batch bills modified premium plus fee, whereas the quote screen also includes any capped endorsement charge. | P0000068: COBOL total $1,280.00 versus Pharo $1,405.00 on equal modified and fee; P0000001 agrees without endorsements. | amber |
| [R101](citations.md#r101) | Adding insureds on a non-GL policy does not add a charge. | No fixture reaches this condition. | unproven |
| [R102](citations.md#r102) | Equipment breakdown adds no charge outside PR. | P0000073 requests equipment on GL, but the cap masks it; no fixture has a discriminating output. | unproven |
| [R103](citations.md#r103) | Requesting a waiver of subrogation on PR does not add a charge. | No fixture reaches this condition. | unproven |
| [R104](citations.md#r104) | Hired and non-owned auto adds no charge outside GL. | P0000072 (CA with HNOA selected): only the $61.00 waiver is charged in Pharo; COBOL adds no endorsements. | proven |

## Decisions: keep both legacy outcomes

**R94 — When should the floor apply?** These are all five differences in the six shared rating fields. Modified premium and minimum flag are shown together.

| Golden policy | COBOL modified / flag | Pharo modified / flag | What distinguishes the order |
| --- | ---: | ---: | --- |
| P0000065 | $500.00 / Y | $401.07 / N | Schedule and package credits lower an initially above-minimum GL premium below $500. |
| P0000066 | $350.00 / Y | $282.63 / Y | Pharo floors PR at $350 before later schedule and package credits. |
| P0000067 | $554.40 / N | $600.00 / Y | A debit raises GL above $500 without a COBOL floor; Pharo applies the debit to the floor. |
| P0000082 | $1,000.00 / Y | $1,250.00 / Y | The CA surcharge leaves COBOL below $1,000 before its floor; Pharo applies the surcharge to $1,000. |
| P0000200 | $750.00 / Y | $675.00 / Y | A schedule credit lowers Pharo below the $750 GL/CA floor. |

**R42–R45, R95–R96, R98–R100 — Are endorsements a quote-only charge or should the batch bill them too?** The fixed-width batch accepts the endorsement inputs but does not price them; Pharo includes the applicable charges in its total. These are channel-contract differences, not additional differences in the six shared rating fields. R98 and R99 describe the calculation of the same charge, and R100 its effect on the total.

| Golden policy | Charge witnessed | COBOL total | Pharo charge | Pharo total |
| --- | --- | ---: | ---: | ---: |
| P0000068 | Insureds and GL waiver | $1,280.00 | $125.00 | $1,405.00 |
| P0000069 | Insured count capped at three, plus HNOA | $1,280.00 | $270.00 | $1,550.00 |
| P0000070 | Equipment dollar minimum | $385.00 | $75.00 | $460.00 |
| P0000071 | Equipment percentage and rounding | $4,195.00 | $125.00 | $4,320.00 |
| P0000072 | CA waiver with HNOA excluded | $3,085.00 | $61.00 | $3,146.00 |
| P0000073 | Combined cap | $541.00 | $126.50 | $667.50 |
| P0000076 | One elected additional insured | $4,353.44 | $50.00 | $4,403.44 |

**R33 — Is a separate Florida property wind surcharge intended when a PR/WND row is supplied?** The batch would apply a separate last-match factor with no date check; Pharo has no separate surcharge. P0000148 exercises the Florida property gate but cannot distinguish those paths without that row. This is a latent difference, not a golden-output mismatch.

**Intermediate premium rounding is not a disagreement in this run.** R18, R46 and R90–R92 preserve the distinguishing golden outputs; endorsement rounding is separate (R98).

## Exclusivity, paired keys and fallback

- The first failed rating gate makes reject/decline exclusive of subsequent rating, minimum and fee (R01–R04). P0000005 and P0000013 show the early exits; the fixture set has no competing simultaneous failures.
- Eligibility requires line + class + state; state and wildcard are exclusive, and no row allows rating to proceed (R05–R09, R87). P0000040/P0000041 distinguish state, P0000005 uses the wildcard, and no row pair overlaps at exact-state/wildcard priority.
- Class uses line + class and effective date (P0000028/P0000030); territory uses line + territory and effective date (P0000015/P0000020 show different factors for territory 010). Territory source is one of direct T, default D or replacement O (P0000014/P0000018/P0000031). A missing class has no fallback; missing exact and default territory rejects before override. No fixture reaches override after D, CA default D, or same-priority ties.
- Override requires line + class + original requested territory and date, not the defaulted territory (R15–R16, R89). P0000027/P0000031/P0000033 isolate the class and territory keys; P0000034/P0000035 isolate the date gate.
- Minimum uses line + state, then line + wildcard, never both (R36–R40; P0000061/P0000062/P0000063). Every supported line has a wildcard; no fixture reaches no valid minimum row or exact equality.
- Experience branches and deductible bands are each exclusive (P0000045–P0000047 and P0000048–P0000052); schedule bounds cannot both apply (P0000054/P0000057). These adjustments can stack with the package adjustment (P0000089). Eligible endorsement charges can add together, but only one aggregate cap applies (P0000068/P0000073).

## Quote-screen input contract

These are form mappings, not separate actuarial adjustments. [Screen citations](citations.md#quote-screen-input-contract) locate the input and displayed-output paths.

- The screen rates only once a line is submitted; it trims supplied text and uppercases line/state, uses 000 for omitted territory and zero for omitted numerics, parses exposure in dollars to cents and treats checkbox presence as true. P0000066 exercises its exposure, signed schedule and multi-policy mapping; P0000073 exercises multiple selected endorsements. No golden fixture tests omitted field defaults, lowercase or padded inputs as submitted, or a blank form.
- The screen renders status/reason, factor source, base premium, minimum flag, modified premium, endorsements, fee and total. The localhost replay compared all eight displayed fields for every golden policy.
