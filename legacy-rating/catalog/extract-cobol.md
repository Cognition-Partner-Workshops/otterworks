# COBOL batch rule extract

Golden run `INSR_20261124`, base `1b421600`. Scope: `legacy-rating/cobol/` and its input tables; no Pharo or Java claims. Source citations are relative to `legacy-rating/cobol/` for COBOL and `legacy-rating/` for tables.

The repository's COBOL Dockerfile built the unmodified batch, which ran against checked-in `legacy-rating/fixtures/policies.dat` and `legacy-rating/tables/`. The fixture consistency check printed `policies.dat OK (200 policies)`. The batch printed `RATEPREM READ=0000200 OK=0000190 DEC=0000007 REJ=0000003`; the 7 declines were 1 EX01, 1 EX02 and 5 EX04, and the 3 rejections were 1 LN and 2 EX. Output SHA-256: `cf852a562fea6e4b31ff63a0602e4765f9bd8bedbfa65664aad20d46eea868ad`.

Amounts below were decoded using the fields in `copybooks/RATEOUT.cpy` L5-L16, with signed overpunch and implied decimals. **from-table** means the cited row was exercised by COBOL; **unproven** means either COBOL alone evidenced the statement (so it still needs the Pharo run for `proven`) or the cited path had no distinguishing fixture, as noted. COBOL-only extract count: 86 entries, 35 from-table, 51 unproven, 0 proven and 0 amber.

## Validation and underwriting

| ID | Statement | COBOL and table citations | Golden fixture and observed output | Status |
| --- | --- | --- | --- | --- |
| R-COBOL-01 | The batch rejects a policy outside GL, PR and CA with reason LN. | `RATEPREM.cbl:1100-VALIDATE-LINE L276-L281` | P0000013: WC, REJ/LN. | unproven |
| R-COBOL-02 | The batch rejects zero or negative exposure on a supported line with reason EX. | `RATEPREM.cbl:1200-VALIDATE-EXPOSURE L283-L287` | P0000043: −125.00, REJ/EX; P0000044: 0.00, REJ/EX. | unproven |
| R-COBOL-03 | The first failed check in line, exposure, eligibility, class and territory order stops the later checks and premium calculations. | `RATEPREM.cbl:1000-RATE-POLICY L239-L262` | P0000005: DEC/EX01 and no base rate despite an in-force GL/91111 row at `tables/class-factors.dat:8`; P0000013: REJ/LN despite the WC class row at `tables/class-factors.dat:16`. | unproven |
| R-COBOL-04 | A reject or decline carries no fee or total and does not set the minimum flag. | `RATEPREM.cbl:1000-RATE-POLICY L231-L262` | P0000005 and P0000013: fee and total 0.00, minimum flag N. | unproven |
| R-COBOL-05 | Eligibility first looks for a row matching line, class and the policy state. | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY L291-L310`; `tables/line-eligibility.dat:5` | P0000040: CA/7219 NY → DEC/EX04; P0000041: same line and class in IL → OK. No fixture reaches a key with both a state and wildcard row. | unproven |
| R-COBOL-06 | If no exact-state eligibility row matches, the batch uses the same line and class with state `**` when such a row exists. | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY L291-L310`; `tables/line-eligibility.dat:3`, `tables/line-eligibility.dat:4`, `tables/line-eligibility.dat:6` | P0000005: GL/91111 IL → DEC/EX01; P0000042: CA/7911 NY → OK. | unproven |
| R-COBOL-07 | With no line/class/state or line/class/`**` eligibility row, the policy passes the eligibility check. | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY L291-L310`; `tables/line-eligibility.dat:5` (NY only) | P0000041: CA/7219 IL → OK. | unproven |
| R-COBOL-08 | A matching eligibility row coded N declines the policy with that row's reason. | `RATEPREM.cbl:2010-APPLY-ELIGIBILITY L312-L316`; `tables/line-eligibility.dat:3`, `tables/line-eligibility.dat:4`, `tables/line-eligibility.dat:5` | P0000005, P0000009, P0000040: DEC with EX01, EX02, EX04 respectively. | unproven |
| R-COBOL-09 | A matching eligibility row not coded N leaves the policy eligible for further checks. | `RATEPREM.cbl:2010-APPLY-ELIGIBILITY L312-L316`; `tables/line-eligibility.dat:6` | P0000042 uses the Y row and rates OK at 520.0000. | unproven |

## Rate selection and base premium

| ID | Statement | COBOL and table citations | Golden fixture and observed output | Status |
| --- | --- | --- | --- | --- |
| R-COBOL-10 | The base rate comes from the first matching line/class row in force on the effective date, including both endpoints. | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335`; `tables/class-factors.dat:5`, `tables/class-factors.dat:6` | P0000028 on 2026-06-30: 2.1000; P0000030 on 2026-07-01: 2.2500. | unproven |
| R-COBOL-11 | Without an in-force line/class row, the policy is rejected with reason CL. | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335`; `tables/class-factors.dat:3` (example dated key) | No fixture reaches this. | unproven |
| R-COBOL-12 | The batch first uses an in-force factor matching line and requested territory on the effective date, including both endpoints, and records source T. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350`; `tables/territory-factors.dat:6`, `tables/territory-factors.dat:7` | P0000027 on 2026-06-30: 1.200/T; P0000029 on 2026-07-01: 1.350/T; P0000014 explicitly requests 000 and also returns T. | unproven |
| R-COBOL-13 | When the requested territory is missing or out of force, the batch uses an in-force territory 000 row for the same line and records source D. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L361`; `tables/territory-factors.dat:3`, `tables/territory-factors.dat:8`, `tables/territory-factors.dat:12` | P0000018: unknown GL/099 → 1.000/D; P0000023: expired PR/060 → 1.000/D. | unproven |
| R-COBOL-14 | If neither an exact nor a default territory row is in force, the policy is rejected with reason TR before override lookup. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L365`; `RATEPREM.cbl:1000-RATE-POLICY L249-L254`; `tables/territory-factors.dat:3`, `tables/territory-factors.dat:8`, `tables/territory-factors.dat:13` | No fixture reaches this; the current supported lines each have a default territory throughout the dates for which class rates are available. | unproven |
| R-COBOL-15 | The first in-force override matching line, class and the original requested territory replaces rather than multiplies the selected territory factor and records source O. | `RATEPREM.cbl:2300-LOOKUP-OVERRIDE L367-L382`; `tables/overrides.dat:3`, `tables/overrides.dat:4`, `tables/overrides.dat:5`; `tables/territory-factors.dat:6` | P0000031: GL/91580/040 → 1.500/O, not 1.800; P0000027: same line/territory but different class → 1.200/T; P0000033: same line/class but different territory → 1.100/T. No fixture reaches an override after a territory fallback. | unproven |
| R-COBOL-16 | When no override matches all keys and the inclusive date window, the batch leaves the territory factor and its source unchanged. | `RATEPREM.cbl:2300-LOOKUP-OVERRIDE L368-L382`; `tables/overrides.dat:3`, `tables/overrides.dat:4`, `tables/overrides.dat:5` | P0000032: GL override still O on its end date; P0000034 → 1.250/T one day before PR starts vs P0000035 → 1.600/O on its start; P0000037 → 1.550/O on CA end date vs P0000038 → 1.300/T one day after; P0000023 retains D. | unproven |
| R-COBOL-17 | A blank end date keeps a class, territory or override row open after its start date. | `RATEPREM.cbl:0130-OPEN-END-DATE L223-L229`; `RATEPREM.cbl:0100-LOAD-TABLES L109-L189`; `tables/class-factors.dat:6`, `tables/territory-factors.dat:7`, `tables/overrides.dat:4` | P0000030 and P0000029 select the open class and territory rows; P0000091 selects the open override after its start date. | unproven |
| R-COBOL-18 | The batch multiplies exposure by the base rate, rounds to cents, then multiplies by the selected territory factor and rounds the base premium to cents again. | `RATEPREM.cbl:3000-BASE-PREMIUM L384-L387` | P0000092: 754.14 × 0.5200 → 392.15; × 1.150 → base 450.97, not 450.98 from one rounding at the end. | unproven |

## Modifications, minimum and fee

| ID | Statement | COBOL and table citations | Golden fixture and observed output | Status |
| --- | --- | --- | --- | --- |
| R-COBOL-19 | Three or more claims in three years increase premium by 25%. | `RATEPREM.cbl:3100-EXPERIENCE-MOD L389-L398` | P0000047: 3 claims, 867.35 → 1,084.19. | unproven |
| R-COBOL-20 | Zero claims and at least three years in business reduce premium by 10%. | `RATEPREM.cbl:3100-EXPERIENCE-MOD L389-L398` | P0000045: zero claims, 3 years, 867.35 → 780.62. | unproven |
| R-COBOL-21 | Other claim and years-in-business combinations do not change premium. | `RATEPREM.cbl:3100-EXPERIENCE-MOD L389-L398` | P0000046: zero claims, 2 years, stays 867.35; P0000001: one claim, stays 871.50. | unproven |
| R-COBOL-22 | Property and commercial auto get an 8% credit for deductibles of 5,000 or more. | `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT L401-L413` | P0000051 (PR): 575.10 → 529.09; P0000052 (CA): 1,555.50 → 1,431.06. | unproven |
| R-COBOL-23 | Property and commercial auto get a 5% credit for deductibles of 2,500 through 4,999. | `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT L401-L413` | P0000050: 575.10 → 546.35 with deductible 2,500. | unproven |
| R-COBOL-24 | Property and commercial auto get a 2% credit for deductibles of 1,000 through 2,499. | `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT L401-L413` | P0000049: 575.10 → 563.60 with deductible 1,000. | unproven |
| R-COBOL-25 | Property and commercial auto get no credit for deductibles below 1,000. | `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT L401-L413` | P0000048: 575.10 unchanged with deductible 999. | unproven |
| R-COBOL-26 | General liability receives no deductible credit. | `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT L400-L413` | P0000053: GL, deductible 5,000, stays 726.00. | unproven |
| R-COBOL-27 | A schedule adjustment below −25% is applied as −25%. | `RATEPREM.cbl:3300-SCHEDULE-MOD L415-L423` | P0000054: −30%, 730.40 → 547.80, same as P0000055 at −25%. | unproven |
| R-COBOL-28 | A schedule adjustment above +25% is applied as +25%. | `RATEPREM.cbl:3300-SCHEDULE-MOD L415-L423` | P0000057: +40%, 730.40 → 913.00. | unproven |
| R-COBOL-29 | A schedule adjustment between −25% and +25% inclusive is applied as entered. | `RATEPREM.cbl:3300-SCHEDULE-MOD L415-L423` | P0000055: −25% → 547.80; P0000056: +15% → 839.96, both on 730.40. | unproven |
| R-COBOL-30 | General liability and property get a 5% discount when the multi-policy flag is Y. | `RATEPREM.cbl:3400-MULTI-POLICY L425-L429` | P0000058 (GL): 880.00 → 836.00; P0000059 (PR): 760.00 → 722.00. | unproven |
| R-COBOL-31 | General liability and property get no multi-policy discount without a Y flag. | `RATEPREM.cbl:3400-MULTI-POLICY L425-L429` | P0000001 (GL) with N: stays 871.50; P0000006 (PR) with N: stays 570.00. | unproven |
| R-COBOL-32 | Commercial auto does not receive a multi-policy discount even with a Y flag. | `RATEPREM.cbl:3400-MULTI-POLICY L425-L429` | P0000060: CA with Y stays 1,560.00. | unproven |
| R-COBOL-33 | For Florida property, the batch multiplies premium by the last territory row keyed PR/WND, without checking its effective dates, when such a row exists. | `RATEPREM.cbl:3450-WIND-SURCHARGE L431-L443`; `tables/territory-factors.dat:3-15` (no PR/WND row) | No fixture reaches a PR/WND row. | unproven |
| R-COBOL-34 | For Florida property without a PR/WND row, the wind multiplier is 1.000 and does not change premium. | `RATEPREM.cbl:3450-WIND-SURCHARGE L433-L443`; `tables/territory-factors.dat:3-15` (no PR/WND row) | P0000148: PR/FL, base and modified both 3,665.87 with all other modifiers neutral and minimum flag N. | unproven |
| R-COBOL-35 | The wind adjustment is skipped for non-Florida property and for lines other than property. | `RATEPREM.cbl:3450-WIND-SURCHARGE L433-L443`; `tables/territory-factors.dat:3-15` (no PR/WND row) | P0000006 (PR/IL) and P0000001 (GL/IL) are outside the gate; no fixture can distinguish skipping from a 1.000 multiplier with these tables. | unproven |
| R-COBOL-36 | A line/state minimum takes precedence over that line's all-states minimum. | `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L464`; `tables/minimum-premium.dat:3`, `tables/minimum-premium.dat:4`, `tables/minimum-premium.dat:6`, `tables/minimum-premium.dat:7` | P0000061 GL/CA: 440.00 → 750.00/Y vs P0000062 GL/IL: 440.00 → 500.00/Y; P0000063 CA/TX: 884.00 → 1,200.00/Y. | unproven |
| R-COBOL-37 | If no exact line/state minimum exists, the batch uses the same line's `**` minimum when one exists. | `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L464`; `tables/minimum-premium.dat:3`, `tables/minimum-premium.dat:5`, `tables/minimum-premium.dat:6` | P0000062 GL/IL: 500.00/Y; P0000064 PR/FL: 350.00/Y; P0000082 CA without a matching state minimum: 1,000.00/Y. | unproven |
| R-COBOL-38 | If neither an exact nor an all-states minimum matches, premium passes through without a minimum increase. | `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L469`; `tables/minimum-premium.dat:3`, `tables/minimum-premium.dat:5`, `tables/minimum-premium.dat:6` | No fixture reaches this; each supported line has an all-states row. | unproven |
| R-COBOL-39 | When premium after all credits and surcharges is below the selected minimum, the batch raises it to that minimum and sets the flag to Y. | `RATEPREM.cbl:1000-RATE-POLICY L253-L261`; `RATEPREM.cbl:3500-MINIMUM-PREMIUM L445-L469`; `tables/minimum-premium.dat:3`, `tables/minimum-premium.dat:5` | P0000065: 527.73 base → 401.07 after credits → 500.00/Y; P0000066: 361.00 base → 262.36 after credits → 350.00/Y. | unproven |
| R-COBOL-40 | When premium after modifications is at or above the selected minimum, it is not increased and the flag remains N. | `RATEPREM.cbl:1000-RATE-POLICY L235-L238`; `RATEPREM.cbl:3500-MINIMUM-PREMIUM L465-L469`; `tables/minimum-premium.dat:3` | P0000067: base 462.00, then 554.40 after the debit, minimum N; no fixture reaches exact equality. | unproven |
| R-COBOL-41 | The batch adds a flat 35.00 policy fee to the modified premium after the minimum check to produce total premium. | `RATEPREM.cbl:WORKING-STORAGE SECTION L75-L75`; `RATEPREM.cbl:1000-RATE-POLICY L253-L262`; `RATEPREM.cbl:3600-POLICY-FEE L471-L473` | P0000065: 500.00 + 35.00 → 535.00; P0000001: 871.50 + 35.00 → 906.50. | unproven |
| R-COBOL-42 | The additional-insured count does not affect batch premium. | `copybooks/POLREC.cpy L16-L16`; `RATEPREM.cbl:1000-RATE-POLICY L231-L262` | P0000068 (count 2) and P0000069 (count 5) both retain 1,245.00 before the fee without additional charges. | unproven |
| R-COBOL-43 | The equipment endorsement does not affect batch premium. | `copybooks/POLREC.cpy L17-L17`; `RATEPREM.cbl:1000-RATE-POLICY L231-L262` | P0000071: PR, equipment Y, base and modified both 4,160.00 above the minimum. | unproven |
| R-COBOL-44 | The waiver endorsement does not affect batch premium. | `copybooks/POLREC.cpy L18-L18`; `RATEPREM.cbl:1000-RATE-POLICY L231-L262` | P0000068: waiver Y and base and modified both 1,245.00. | unproven |
| R-COBOL-45 | The hired/non-owned auto endorsement does not affect batch premium. | `copybooks/POLREC.cpy L19-L19`; `RATEPREM.cbl:1000-RATE-POLICY L231-L262` | P0000069: hired/non-owned auto Y and base and modified both 1,245.00. | unproven |
| R-COBOL-46 | The batch applies experience, deductible, schedule, multi-policy and wind in that order, rounding each applied step to cents. | `RATEPREM.cbl:1000-RATE-POLICY L253-L261`; `RATEPREM.cbl:3100-EXPERIENCE-MOD L389-L398`; `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT L401-L413`; `RATEPREM.cbl:3300-SCHEDULE-MOD L415-L423`; `RATEPREM.cbl:3400-MULTI-POLICY L425-L429`; `RATEPREM.cbl:3450-WIND-SURCHARGE L433-L443` | P0000089: 1,950.10 × 0.90 × 0.92 × 1.05 × 0.95 gives modified 1,610.64 with step rounding, not 1,610.65 when rounded only once; the non-neutral wind step is not exercised. | unproven |

## Class-rate rows

All rows below use the policy effective date, not the batch date.

| ID | Statement | COBOL and table citations | Golden fixture and observed output | Status |
| --- | --- | --- | --- | --- |
| R-COBOL-47 | GL class 91340 has base rate 4.1500 from 2026-01-01. | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335`; `tables/class-factors.dat:3` | P0000001: 4.1500. | from-table |
| R-COBOL-48 | GL class 91580 has base rate 6.2000 from 2026-01-01. | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335`; `tables/class-factors.dat:4` | P0000002: 6.2000. | from-table |
| R-COBOL-49 | GL class 41650 has base rate 2.1000 from 2026-01-01 through 2026-06-30. | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335`; `tables/class-factors.dat:5` | P0000028: 2.1000 on 2026-06-30. | from-table |
| R-COBOL-50 | GL class 41650 has base rate 2.2500 from 2026-07-01. | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335`; `tables/class-factors.dat:6` | P0000030: 2.2500 on 2026-07-01. | from-table |
| R-COBOL-51 | GL class 18501 has base rate 1.1000 from 2026-01-01. | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335`; `tables/class-factors.dat:7` | P0000004: 1.1000. | from-table |
| R-COBOL-52 | The table lists GL class 91111 at 9.7500 from 2026-01-01, but the all-states eligibility decline prevents using that rate. | `RATEPREM.cbl:1000-RATE-POLICY L243-L248`; `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335`; `tables/class-factors.dat:8`; `tables/line-eligibility.dat:3` | P0000005: DEC/EX01; no fixture reaches this class-rate row. | unproven |
| R-COBOL-53 | PR class 0311 has base rate 0.3800 from 2026-01-01. | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335`; `tables/class-factors.dat:9` | P0000006: 0.3800. | from-table |
| R-COBOL-54 | PR class 0702 has base rate 0.5200 from 2026-01-01. | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335`; `tables/class-factors.dat:10` | P0000007: 0.5200. | from-table |
| R-COBOL-55 | PR class 0900 has base rate 0.7100 from 2026-01-01. | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335`; `tables/class-factors.dat:11` | P0000008: 0.7100. | from-table |
| R-COBOL-56 | The table lists PR class 0567 at 0.4400 from 2026-01-01, but the all-states eligibility decline prevents using that rate. | `RATEPREM.cbl:1000-RATE-POLICY L243-L248`; `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335`; `tables/class-factors.dat:12`; `tables/line-eligibility.dat:4` | P0000009: DEC/EX02; no fixture reaches this class-rate row. | unproven |
| R-COBOL-57 | CA class 7398 has base rate 610.0000 from 2026-01-01. | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335`; `tables/class-factors.dat:13` | P0000010: 610.0000. | from-table |
| R-COBOL-58 | CA class 7219 has base rate 1,450.0000 from 2026-01-01 where eligible. | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335`; `tables/class-factors.dat:14`; `tables/line-eligibility.dat:5` | P0000011: 1,450.0000. | from-table |
| R-COBOL-59 | CA class 7911 has base rate 520.0000 from 2026-01-01. | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335`; `tables/class-factors.dat:15` | P0000012: 520.0000. | from-table |
| R-COBOL-60 | The table lists WC class 8810 at 0.2500 from 2026-01-01, but the batch rejects WC before it looks for a class rate. | `RATEPREM.cbl:1000-RATE-POLICY L239-L248`; `RATEPREM.cbl:1100-VALIDATE-LINE L276-L281`; `tables/class-factors.dat:16` | P0000013: REJ/LN; no fixture reaches this class-rate row. | unproven |

## Eligibility rows

| ID | Statement | COBOL and table citations | Golden fixture and observed output | Status |
| --- | --- | --- | --- | --- |
| R-COBOL-61 | GL class 91111 is declined in every state with reason EX01. | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY L291-L310`; `RATEPREM.cbl:2010-APPLY-ELIGIBILITY L312-L316`; `tables/line-eligibility.dat:3` | P0000005: DEC/EX01. | from-table |
| R-COBOL-62 | PR class 0567 is declined in every state with reason EX02. | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY L291-L310`; `RATEPREM.cbl:2010-APPLY-ELIGIBILITY L312-L316`; `tables/line-eligibility.dat:4` | P0000009: DEC/EX02. | from-table |
| R-COBOL-63 | CA class 7219 is declined in NY with reason EX04. | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY L291-L310`; `RATEPREM.cbl:2010-APPLY-ELIGIBILITY L312-L316`; `tables/line-eligibility.dat:5` | P0000040: DEC/EX04; P0000041 in IL is OK. | from-table |
| R-COBOL-64 | CA class 7911 has an all-states eligibility allowance. | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY L291-L310`; `RATEPREM.cbl:2010-APPLY-ELIGIBILITY L312-L316`; `tables/line-eligibility.dat:6` | P0000042 matches the Y row and is OK; OK alone cannot distinguish explicit allowance from no row. | from-table |

## Territory-factor rows

| ID | Statement | COBOL and table citations | Golden fixture and observed output | Status |
| --- | --- | --- | --- | --- |
| R-COBOL-65 | GL territory 000 has a factor of 1.000 from 2026-01-01. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L361`; `tables/territory-factors.dat:3` | P0000014: 1.000/T; P0000018 defaults to 1.000/D. | from-table |
| R-COBOL-66 | GL territory 010 has a factor of 0.950 from 2026-01-01. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350`; `tables/territory-factors.dat:4` | P0000015: 0.950/T. | from-table |
| R-COBOL-67 | GL territory 020 has a factor of 1.100 from 2026-01-01. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350`; `tables/territory-factors.dat:5` | P0000016: 1.100/T. | from-table |
| R-COBOL-68 | GL territory 040 has a factor of 1.200 from 2026-01-01 through 2026-06-30 when not overridden. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350`; `tables/territory-factors.dat:6` | P0000027: 1.200/T on 2026-06-30. | from-table |
| R-COBOL-69 | GL territory 040 has a factor of 1.350 from 2026-07-01 when not overridden. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350`; `tables/territory-factors.dat:7` | P0000029: 1.350/T on 2026-07-01. | from-table |
| R-COBOL-70 | PR territory 000 has a factor of 1.000 from 2026-01-01. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L361`; `tables/territory-factors.dat:8` | P0000019: 1.000/T; P0000023 defaults to 1.000/D. | from-table |
| R-COBOL-71 | PR territory 010 has a factor of 0.900 from 2026-01-01. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350`; `tables/territory-factors.dat:9` | P0000020: 0.900/T. | from-table |
| R-COBOL-72 | PR territory 030 has a factor of 1.250 from 2026-01-01 when not overridden. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350`; `tables/territory-factors.dat:10` | P0000021: 1.250/T. | from-table |
| R-COBOL-73 | PR territory 040 has a factor of 1.150 from 2026-01-01. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350`; `tables/territory-factors.dat:11` | P0000022: 1.150/T. | from-table |
| R-COBOL-74 | The PR territory 060 factor of 1.400 only applies from 2025-01-01 through 2025-12-31, before any property class rate is in force in the current table. | `RATEPREM.cbl:1000-RATE-POLICY L246-L251`; `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L361`; `tables/territory-factors.dat:12`; `tables/class-factors.dat:9-12` | P0000023 is after expiration and uses 1.000/D; no fixture reaches the 1.400 factor. | unproven |
| R-COBOL-75 | CA territory 000 has a factor of 1.000 from 2026-01-01. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L361`; `tables/territory-factors.dat:13` | P0000024: 1.000/T; no fixture reaches the CA default path. | from-table |
| R-COBOL-76 | CA territory 020 has a factor of 1.300 from 2026-01-01 when not overridden. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350`; `tables/territory-factors.dat:14` | P0000025: 1.300/T. | from-table |
| R-COBOL-77 | CA territory 050 has a factor of 0.850 from 2026-01-01. | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350`; `tables/territory-factors.dat:15` | P0000026: 0.850/T. | from-table |

## Minimum-premium rows

| ID | Statement | COBOL and table citations | Golden fixture and observed output | Status |
| --- | --- | --- | --- | --- |
| R-COBOL-78 | GL has a 500.00 all-states minimum when there is no state-specific row. | `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L469`; `tables/minimum-premium.dat:3` | P0000062: 500.00/Y. | from-table |
| R-COBOL-79 | GL in CA has a 750.00 minimum. | `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L469`; `tables/minimum-premium.dat:4` | P0000061: 750.00/Y. | from-table |
| R-COBOL-80 | PR has a 350.00 all-states minimum. | `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L469`; `tables/minimum-premium.dat:5` | P0000064: 350.00/Y. | from-table |
| R-COBOL-81 | CA has a 1,000.00 all-states minimum when there is no state-specific row. | `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L469`; `tables/minimum-premium.dat:6` | P0000082: 1,000.00/Y. | from-table |
| R-COBOL-82 | CA in TX has a 1,200.00 minimum. | `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L469`; `tables/minimum-premium.dat:7` | P0000063: 1,200.00/Y. | from-table |
| R-COBOL-83 | The table lists a 250.00 minimum for WC, but the batch rejects WC before the minimum check. | `RATEPREM.cbl:1000-RATE-POLICY L239-L262`; `RATEPREM.cbl:1100-VALIDATE-LINE L276-L281`; `tables/minimum-premium.dat:8` | P0000013: REJ/LN; no fixture reaches this minimum row. | unproven |

## Override rows

| ID | Statement | COBOL and table citations | Golden fixture and observed output | Status |
| --- | --- | --- | --- | --- |
| R-COBOL-84 | GL class 91580 in territory 040 has a replacement factor of 1.500 from 2026-01-01 through 2026-12-31. | `RATEPREM.cbl:2300-LOOKUP-OVERRIDE L368-L382`; `tables/overrides.dat:3` | P0000031 and P0000032: 1.500/O; P0000032 is on the end date. | from-table |
| R-COBOL-85 | PR class 0702 in territory 030 has a replacement factor of 1.600 from 2026-03-01. | `RATEPREM.cbl:2300-LOOKUP-OVERRIDE L368-L382`; `tables/overrides.dat:4` | P0000035: 1.600/O on the start date; P0000034: 1.250/T the previous day. | from-table |
| R-COBOL-86 | CA class 7219 in territory 020 has a replacement factor of 1.550 from 2026-01-01 through 2026-09-30 where eligible. | `RATEPREM.cbl:2300-LOOKUP-OVERRIDE L368-L382`; `tables/overrides.dat:5`; `tables/line-eligibility.dat:5` | P0000037: 1.550/O on the end date; P0000038: 1.300/T the next day. | from-table |

## Exclusivity, paired keys and coverage limits

- Eligibility uses line/class/state, then line/class/`**` only if no state row matched (R-COBOL-05–09; P0000040, P0000041, P0000042). Class uses line/class/date (R-COBOL-10; P0000028, P0000030); territory uses line/territory/date (R-COBOL-12–14; P0000018, P0000023, P0000027, P0000029). The requested-territory and default paths are exclusive; an exact 000 is still T. An override uses line/class/requested territory/date and replaces T or D rather than stacking with it (R-COBOL-15–16; P0000031, P0000033, P0000027). Minimum selects exactly one line/state or line/`**` row (R-COBOL-36–38; P0000061, P0000062, P0000063). No fixture reaches multiple eligible rows in one lookup pass with the same active key; except for wind, lookups stop at the first match in file order.
- Experience branches are mutually exclusive (P0000045–P0000047); deductible bands are exclusive (P0000048–P0000052), and the upper and lower schedule bounds cannot both apply (P0000054–P0000057). Experience, deductible, schedule and multi-policy can all modify one policy (P0000089). A pre-rating reject/decline is exclusive of minimum and fees (P0000005, P0000013).
- Loaded rows never selected in the 200 golden policies: class rows GL/91111 and PR/0567 are blocked by eligibility, WC/8810 class and WC minimum by line validation, and PR/060 territory is expired for all rateable PR dates (R-COBOL-52, 56, 60, 74, 83). The potential PR/WND row is absent, not merely unselected (R-COBOL-33).

## Candidates for the Pharo cross-check

- **Minimum ordering:** compare P0000065, P0000066 and P0000067 against the quote screen before accepting equivalence; COBOL applies the floor after both credits and debits (R-COBOL-39–41).
- **Endorsements:** the batch record accepts the fields but the batch has no endorsement charges (R-COBOL-42–45; P0000068, P0000069, P0000071, P0000072 and P0000073). Check the quote path separately, particularly P0000071 and P0000073 where a floor does not mask a charge.
- **Wind and rounding:** confirm whether the quote path has equivalent Florida wind handling and whether it rounds at the same intermediate steps (R-COBOL-18, 33–35, 46; P0000148, P0000092, P0000089). The checked-in tables cannot expose a non-neutral wind factor.

These are candidates, not findings of cross-stack disagreement or choices about which stack should win.
