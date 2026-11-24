# Pharo quote-screen rule extract

Source: `demo-insrules` at `1b421600226126008dd2a6a26dd47e391ad18a82`. This is the Pharo contribution to Phase 1; COBOL source citations belong to the independent batch extract and will be joined when the catalog is merged. All input and citation paths below are relative to `legacy-rating/`.

## Execution evidence

Replayed all 200 records in `fixtures/policies.dat` as GET requests against `InsQuoteScreen` on localhost, mapping fixed-width fields to their corresponding form fields and restoring fixture IDs to the responses because the screen uses `SCREEN` internally. Every rendered quote matched the headless Pharo output on all displayed fields (200/200; 190 OK, 7 DEC, 3 REJ). Headless Pharo output SHA-256: `adfad3afab8556a2b2307bf023dd8718a5da712107d42d7ffa96f34e327c8e96`.

For shared-rule evidence only, ran the checked-in COBOL batch on the same inputs and compared with `parity/driver.py`'s `compare` and `RATING_FIELDS` (status, reason, base, modified, minimum, factor source): 195 matched, 5 differed, all in modified premium and/or the minimum flag. All recorded witnesses for shared rules agree on the field proving the indicated rule. Endorsements exist only on the quote path and are excluded from that comparison. COBOL raw output SHA-256: `cf852a562fea6e4b31ff63a0602e4765f9bd8bedbfa65664aad20d46eea868ad`.

```sh
mkdir -p legacy-rating/build
INSRULES_SCREEN_PORT=18091 docker compose -f docker-compose.insrules.yml -p insrules-pharo up -d --build quote-screen
docker compose -f docker-compose.insrules.yml -p insrules-pharo exec -T quote-screen ./run.sh quote /estate/fixtures/policies.dat /estate/build/pharo-extract.txt
docker compose -f docker-compose.insrules.yml -p insrules-pharo --profile batch run --rm --build rating-batch /estate/fixtures/policies.dat /estate/build/cobol-for-pharo.dat
# HTTP equivalent of P0000066 (blank checkboxes are omitted):
curl -fsS 'http://127.0.0.1:18091/?line=PR&state=IL&class=0311&territory=000&effective=20260315&exposure=950.00&years=06&claims=00&deductible=00500&schedule=-15&addl=00&multi=on'
```

Money in evidence is expressed in integer cents unless marked with a dollar sign. Table evidence `base=…` is the displayed base after the factor, not the class rate alone. `E` = `smalltalk/src/InsRating/InsQuoteEngine.class.st`, `T` = `smalltalk/src/InsRating/InsRatingTables.class.st`, `Q` = `smalltalk/src/InsRating/InsQuote.class.st`. Status: **proven** = shared behavior witnessed in both outputs; **from-table** = executed table-backed rule; **amber** = legacy disagreement or Pharo-only charge/contract to retain, not a proposed resolution; **unproven** = no fixture output demonstrates that condition.

## Gate and lookup rules

| ID | Rule | Pharo citation (file:lines) | Table row(s) | Executed fixture and result | Status |
| --- | --- | --- | --- | --- | --- |
| R-PH-01 | Only GL, PR and CA are accepted lines; any other line is rejected as LN. | `InsQuoteEngine>>validateLine:into:` (E:59–61) | — | P0000013 (WC), REJ/LN; P0000001, P0000006, P0000010, OK | proven |
| R-PH-02 | A policy with zero or negative exposure is rejected as EX. | `InsQuoteEngine>>validateExposure:into:` (E:64–66) | — | P0000043 (negative), P0000044 (zero), both REJ/EX | proven |
| R-PH-03 | A rejected or declined quote carries no premium or fee. | `InsQuoteEngine>>quote:` (E:28–39); `InsQuote>>initialize` (Q:13–17) | — | P0000005, P0000013, P0000043: base, modified, endorsements, fee and total are zero on screen; shared status, reason, base and modified agree | proven |
| R-PH-04 | Eligibility uses line and class together, checks for the policy's state and falls back to the all-states row. | `InsQuoteEngine>>checkEligibility:into:` (E:69–76) | `tables/line-eligibility.dat:3–6` | P0000005, DEC/EX01 via wildcard; P0000040, DEC/EX04 via exact NY; P0000041, OK in IL | from-table |
| R-PH-05 | When both a matching state and an all-states eligibility row exist, the state row wins. | `InsQuoteEngine>>checkEligibility:into:` (E:69–76) | `tables/line-eligibility.dat:3–6` | No fixture reaches this; the loaded table has no such pair | unproven |
| R-PH-06 | When no exact-state or all-states eligibility row matches, the policy proceeds to class rating. | `InsQuoteEngine>>checkEligibility:into:` (E:69–76) | `tables/line-eligibility.dat:3–6` | P0000041, CA 7219 IL, OK/base=435000 despite NY exclusion | from-table |
| R-PH-07 | GL class 91111 is declined in all states with EX01. | `InsQuoteEngine>>checkEligibility:into:` (E:69–76) | `tables/line-eligibility.dat:3` | P0000005, DEC/EX01 | from-table |
| R-PH-08 | PR class 0567 is declined in all states with EX02. | `InsQuoteEngine>>checkEligibility:into:` (E:69–76) | `tables/line-eligibility.dat:4` | P0000009, DEC/EX02 | from-table |
| R-PH-09 | CA class 7219 is declined in NY with EX04. | `InsQuoteEngine>>checkEligibility:into:` (E:69–76) | `tables/line-eligibility.dat:5` | P0000040, DEC/EX04; P0000041 (IL), OK | from-table |
| R-PH-10 | CA class 7911 is eligible in every state, subject to the other quote gates. | `InsQuoteEngine>>checkEligibility:into:` (E:69–76) | `tables/line-eligibility.dat:6` | P0000012, OK/base=156000 | from-table |
| R-PH-11 | The class rate comes from an in-force row matching both the line and the class. | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:3–16` | P0000028/P0000030 (same GL/class/exposure/territory, opposite sides of the rate change), base=79800/85500 | from-table |
| R-PH-12 | A missing in-force class row causes rejection CL without a class-rate fallback. | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:3–16` | No fixture reaches this | unproven |
| R-PH-13 | An in-force row matching the line and submitted territory supplies factor source T, including when the submitted territory is 000. | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:3–15` | P0000014, direct 000/T; P0000017, direct 040/T | from-table |
| R-PH-14 | A missing or out-of-force submitted territory falls back to the in-force 000 row for the same line and uses source D. | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:3,8,12,13` | P0000018, unknown GL 099/D/base=74700; P0000023, expired PR 060/D/base=45600 | from-table |
| R-PH-15 | The quote rejects as TR if both the submitted territory and its line's 000 default lack an in-force row. | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:3,8,13` | No fixture reaches this | unproven |
| R-PH-16 | Class rates, territory factors and overrides include both the effective start date and the end date, with blank end dates treated as open-ended through 99999999. | `InsRatingTables>>row:from:inForceOn:` (T:46–53); `InsQuoteEngine>>lookupClassRate:into:` (E:80–87), `lookupTerritory:into:` (E:90–104), `lookupOverride:into:` (E:107–117) | `tables/class-factors.dat:5–6`; `tables/territory-factors.dat:6–7`; `tables/overrides.dat:3–5` | P0000027–P0000030 (June/July boundaries); P0000032 (GL end); P0000034/P0000035 (PR day before/start); P0000037/P0000038 (CA end/day after) | from-table |
| R-PH-17 | An in-force override matching the original line, class and territory replaces the resolved territory factor and sets source O rather than multiplying the factors together. | `InsQuoteEngine>>lookupOverride:into:` (E:107–117) | `tables/overrides.dat:3–5`; `tables/territory-factors.dat:6–7,10,14` | P0000031, O/base=139965; P0000027, same line/territory but different class, remains T; P0000033, same line/class but other territory, remains T | from-table |
| R-PH-18 | If no override matches all its keys and dates, the resolved territory factor and source are retained. | `InsQuoteEngine>>lookupOverride:into:` (E:107–117) | `tables/overrides.dat:3–5`; `tables/territory-factors.dat:3,5,10,14` | P0000034/P0000038 retain T outside override dates; P0000018 retains D without an override | from-table |
| R-PH-19 | When rows tie on keys, dates and precedence, the first matching data row in file order wins. | `InsRatingTables>>rowsIn:` (T:39–43); `InsQuoteEngine>>checkEligibility:into:` (E:69–76), `lookupClassRate:into:` (E:80–87), `lookupTerritory:into:` (E:90–104), `lookupOverride:into:` (E:107–117), `applyMinimum:premium:quote:` (E:147–157) | `tables/class-factors.dat:5–6` and `tables/territory-factors.dat:6–7` are adjacent, not overlapping | No fixture reaches a tie; the loaded tables contain none | unproven |

## Premium calculation

| ID | Rule | Pharo citation (file:lines) | Table row(s) | Executed fixture and result | Status |
| --- | --- | --- | --- | --- | --- |
| R-PH-20 | The base premium is exposure times the four-decimal class rate rounded to cents, then multiplied by the three-decimal territory or override factor and rounded again. | `InsQuoteEngine>>basePremium:quote:` (E:120–124); `InsQuoteEngine>>lookupClassRate:into:` (E:80–87), `lookupTerritory:into:` (E:90–104) | `tables/class-factors.dat:10`; `tables/territory-factors.dat:11` | P0000092, base=45097 with two rounds rather than 45098 with one | proven |
| R-PH-21 | Each premium step that rounds to cents rounds a half cent up. | `InsQuoteEngine>>round:scale:` (E:22–25); `basePremium:quote:` (E:120–124) | `tables/class-factors.dat:7`; `tables/territory-factors.dat:4` | P0000065, rate step=55550 and factored amount=52772.5, base=52773 in both stacks | proven |
| R-PH-22 | Three or more claims in the experience window add 25% to the premium. | `InsQuoteEngine>>experienceMod:premium:` (E:127–133); `InsQuoteScreen>>pageFor:quote:` (`smalltalk/src/InsRating/InsQuoteScreen.class.st:83`) | — | P0000047 (three claims), base=86735, modified=108419 | proven |
| R-PH-23 | A policy with zero claims and at least three years in business gets a 10% experience credit. | `InsQuoteEngine>>experienceMod:premium:` (E:127–133) | — | P0000045 (zero claims, three years), base=86735, modified=78062 | proven |
| R-PH-24 | All other claim and years-in-business combinations leave the premium unchanged at the experience step. | `InsQuoteEngine>>experienceMod:premium:` (E:127–133) | — | P0000046 (zero claims, two years), base=modified=86735; P0000001 (one claim), base=modified=87150 | proven |
| R-PH-25 | GL does not receive a deductible credit. | `InsQuoteEngine>>deductibleCredit:premium:` (E:136–144) | — | P0000053 (deductible $5,000), base=modified=72600 | proven |
| R-PH-26 | PR and CA deductibles below $1,000 do not receive a deductible credit. | `InsQuoteEngine>>deductibleCredit:premium:` (E:136–144) | — | P0000048 (PR/$999), base=modified=57510; P0000010 (CA/$500), base=modified=183000 | proven |
| R-PH-27 | PR and CA deductibles of $1,000 through $2,499 receive a 2% credit. | `InsQuoteEngine>>deductibleCredit:premium:` (E:136–144) | — | P0000049 (PR/$1,000), modified=56360; P0000094 (CA/$1,000, schedule −20%), modified=591136 | proven |
| R-PH-28 | PR and CA deductibles of $2,500 through $4,999 receive a 5% credit. | `InsQuoteEngine>>deductibleCredit:premium:` (E:136–144) | — | P0000050 (PR/$2,500), modified=54635; P0000077 (CA/$2,500), modified=413250 | proven |
| R-PH-29 | PR and CA deductibles of $5,000 or more receive an 8% credit. | `InsQuoteEngine>>deductibleCredit:premium:` (E:136–144) | — | P0000051 (PR), modified=52909; P0000052 (CA), modified=143106 | proven |
| R-PH-30 | Experience is applied and rounded before any deductible credit. | `InsQuoteEngine>>rate:into:` (E:43–55), `experienceMod:premium:` (E:127–133), `deductibleCredit:premium:` (E:136–144) | — | P0000097, modified=956056, distinguishes the reversed rounding order | proven |
| R-PH-31 | The minimum uses the exact state for the line when present and otherwise uses the line's all-states minimum. | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:3–7` | P0000061/P0000062 (same GL base=44000), CA/IL modified=75000/50000 | from-table |
| R-PH-32 | A quote is left unfloored when neither an exact-state nor all-states minimum exists for its line. | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:3–8` | No fixture reaches this; every accepted line has a wildcard | unproven |
| R-PH-33 | A premium strictly below the selected minimum is raised to that amount and marked as floored. | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:3–7` | P0000062, minimum yes, modified=50000 | from-table |
| R-PH-34 | A premium above the minimum passes the minimum step unchanged and is not marked as floored. | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:3` | P0000001, base=modified=87150, minimum no | from-table |
| R-PH-35 | The quote screen applies its minimum after experience and deductible adjustments but before schedule and multi-policy adjustments, so later credits can take the result below the minimum. | `InsQuoteEngine>>rate:into:` (E:43–55), `applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:3–6` | P0000065, P0000066, P0000067, P0000082, P0000200; see five differences below | amber |
| R-PH-36 | A schedule modifier below −25% is limited to a 25% credit. | `InsQuoteEngine>>scheduleMod:premium:` (E:160–164) | — | P0000054 (−30%) and P0000055 (−25%), both modified=54780 | proven |
| R-PH-37 | A schedule modifier above +25% is limited to a 25% surcharge. | `InsQuoteEngine>>scheduleMod:premium:` (E:160–164) | — | P0000057 (+40%), 73040 → 91300 | proven |
| R-PH-38 | A schedule modifier from −25% through +25% multiplies the premium by one plus that signed percentage. | `InsQuoteEngine>>scheduleMod:premium:` (E:160–164) | — | P0000056 (+15%), 73040 → 83996; P0000055 (−25%), 73040 → 54780; P0000001 (zero), unchanged | proven |
| R-PH-39 | A GL or PR policy with the multi-policy flag receives a 5% credit. | `InsQuoteEngine>>multiPolicy:premium:` (E:167–170) | — | P0000058 (GL), 88000 → 83600; P0000059 (PR), 76000 → 72200 | proven |
| R-PH-40 | A CA policy or a policy without the multi-policy flag gets no multi-policy credit. | `InsQuoteEngine>>multiPolicy:premium:` (E:167–170) | — | P0000060 (CA, flagged), base=modified=156000; P0000001 (GL, unflagged), base=modified=87150 | proven |
| R-PH-41 | The schedule-adjusted amount is rounded before applying any multi-policy credit. | `InsQuoteEngine>>rate:into:` (E:43–55), `scheduleMod:premium:` (E:160–164), `multiPolicy:premium:` (E:167–170) | — | P0000076, modified=431844 versus 431845 with reversed rounding order | proven |
| R-PH-42 | Each successfully rated policy has a flat $35 fee. | `InsQuoteEngine>>rate:into:` (E:43–55), `policyFee` (E:195) | — | P0000001, screen fee=3500 and COBOL raw fee=03500 | proven |

## Quote-only endorsements and total

These charges do not have an endorsement field on the COBOL batch contract; the five shared-field differences below do not count endorsements. There were 73 Pharo quotes with a nonzero endorsement charge.

| ID | Rule | Pharo citation (file:lines) | Executed fixture and result | Status |
| --- | --- | --- | --- | --- |
| R-PH-43 | GL charges $50 per additional insured, up to three insureds. | `InsQuoteEngine>>endorsements:premium:` (E:173–186, especially 178–179) | P0000076 (one), endorsement=5000; P0000069 (five with HNOA), 15000 + 12000 = 27000 | amber |
| R-PH-44 | Negative additional-insured counts are treated as zero. | `InsQuoteEngine>>endorsements:premium:` (E:178–179) | No fixture reaches this | unproven |
| R-PH-45 | PR equipment breakdown costs 3% of the modified premium when that exceeds $75. | `InsQuoteEngine>>endorsements:premium:` (E:180–181); `wholeDollars:` (E:190–192) | P0000071, modified=416000, endorsement=12500 | amber |
| R-PH-46 | PR equipment breakdown costs at least $75 when selected. | `InsQuoteEngine>>endorsements:premium:` (E:180–181) | P0000070, modified=35000, endorsement=7500 instead of 1050 | amber |
| R-PH-47 | A waiver of subrogation on GL or CA costs 2% of the modified premium. | `InsQuoteEngine>>endorsements:premium:` (E:182–183); `wholeDollars:` (E:190–192) | P0000068 (GL), 10000 + 2500 = 12500; P0000072 (CA), endorsement=6100 | amber |
| R-PH-48 | Hired and non-owned auto costs $120 on GL and is not charged on other lines. | `InsQuoteEngine>>endorsements:premium:` (E:184–185) | P0000069 (GL), 15000 + 12000 = 27000; P0000072 (CA with HNOA checked), only waiver=6100 | amber |
| R-PH-49 | Percentage-based charges are rounded to cents and then to whole dollars before being added. | `InsQuoteEngine>>endorsements:premium:` (E:180–183), `wholeDollars:` (E:190–192), `round:scale:` (E:22–25) | P0000071, 12480 cents rounds to 12500; P0000068, waiver=2490 rounds to 2500 | amber |
| R-PH-50 | The sum of applicable endorsements is capped at 25% of the modified premium rounded to cents. | `InsQuoteEngine>>endorsements:premium:` (E:173–187) | P0000073, uncapped sum=28000, capped charge=12650 on modified=50600 | amber |
| R-PH-51 | A quote's total is its modified premium plus the capped endorsement charge and the policy fee. | `InsQuoteEngine>>rate:into:` (E:43–55) | P0000068, Pharo 124500 + 12500 + 3500 = 140500 versus COBOL raw total=128000 | amber |
| R-PH-52 | Adding insureds on a non-GL policy does not add a charge. | `InsQuoteEngine>>endorsements:premium:` (E:178–179) | No fixture reaches this | unproven |
| R-PH-53 | Equipment breakdown adds no charge outside PR. | `InsQuoteEngine>>endorsements:premium:` (E:180–181) | P0000073 selects it on GL but the cap masks the result; no fixture reaches this with a discriminating output | unproven |
| R-PH-90 | Requesting a waiver of subrogation on PR does not add a charge. | `InsQuoteEngine>>endorsements:premium:` (E:182–183) | No fixture reaches this | unproven |

## Rate and minimum table rows

Each line below is a distinct keyed rule. E methods retain the same file paths as above; dates use `InsRatingTables>>row:from:inForceOn:` (T:46–53).

| ID | Rule | Pharo citation (file:lines) | Table row | Executed fixture and result | Status |
| --- | --- | --- | --- | --- | --- |
| R-PH-54 | GL class 91340 has a base rate of 4.1500 from 2026-01-01. | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:3` | P0000001, base=87150 | from-table |
| R-PH-55 | GL class 91580 has a base rate of 6.2000 from 2026-01-01. | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:4` | P0000002, base=130200 | from-table |
| R-PH-56 | GL class 41650 has a base rate of 2.1000 from 2026-01-01 through 2026-06-30. | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:5` | P0000028, base=79800 | from-table |
| R-PH-57 | GL class 41650 has a base rate of 2.2500 from 2026-07-01. | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:6` | P0000030, base=85500 | from-table |
| R-PH-58 | GL class 18501 has a base rate of 1.1000 from 2026-01-01. | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:7` | P0000004, base=23100 | from-table |
| R-PH-59 | PR class 0311 has a base rate of 0.3800 from 2026-01-01. | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:9` | P0000006, base=57000 | from-table |
| R-PH-60 | PR class 0702 has a base rate of 0.5200 from 2026-01-01. | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:10` | P0000007, base=78000 | from-table |
| R-PH-61 | PR class 0900 has a base rate of 0.7100 from 2026-01-01. | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:11` | P0000008, base=106500 | from-table |
| R-PH-62 | CA class 7398 has a base rate of 610.0000 from 2026-01-01. | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:13` | P0000010, base=183000 | from-table |
| R-PH-63 | CA class 7219 has a base rate of 1450.0000 from 2026-01-01 for eligible policies. | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:14` | P0000011, base=435000 | from-table |
| R-PH-64 | CA class 7911 has a base rate of 520.0000 from 2026-01-01. | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:15` | P0000012, base=156000 | from-table |
| R-PH-65 | The GL default territory 000 factor is 1.000 from 2026-01-01. | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:3` | P0000014/P0000018, base=74700, T/D | from-table |
| R-PH-66 | GL territory 010 has factor 0.950 from 2026-01-01. | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:4` | P0000015, base=70965/T | from-table |
| R-PH-67 | GL territory 020 has factor 1.100 from 2026-01-01. | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:5` | P0000016, base=82170/T | from-table |
| R-PH-68 | GL territory 040 has factor 1.200 from 2026-01-01 through 2026-06-30. | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:6` | P0000027, base=149400/T | from-table |
| R-PH-69 | GL territory 040 has factor 1.350 from 2026-07-01. | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:7` | P0000029, base=168075/T | from-table |
| R-PH-70 | The PR default territory 000 factor is 1.000 from 2026-01-01. | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:8` | P0000019/P0000023, base=45600, T/D | from-table |
| R-PH-71 | PR territory 010 has factor 0.900 from 2026-01-01. | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:9` | P0000020, base=41040/T | from-table |
| R-PH-72 | PR territory 030 has factor 1.250 from 2026-01-01. | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:10` | P0000021, base=57000/T | from-table |
| R-PH-73 | PR territory 040 has factor 1.150 from 2026-01-01. | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:11` | P0000022, base=52440/T | from-table |
| R-PH-74 | The CA default territory 000 factor is 1.000 from 2026-01-01. | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:13` | P0000024, base=122000/T | from-table |
| R-PH-75 | CA territory 020 has factor 1.300 from 2026-01-01. | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:14` | P0000025, base=158600/T | from-table |
| R-PH-76 | CA territory 050 has factor 0.850 from 2026-01-01. | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:15` | P0000026, base=103700/T | from-table |
| R-PH-77 | GL class 91580 in territory 040 uses override factor 1.500 from 2026-01-01 through 2026-12-31. | `InsQuoteEngine>>lookupOverride:into:` (E:107–117) | `tables/overrides.dat:3` | P0000031/P0000032, base=139965/O | from-table |
| R-PH-78 | PR class 0702 in territory 030 uses override factor 1.600 from 2026-03-01. | `InsQuoteEngine>>lookupOverride:into:` (E:107–117) | `tables/overrides.dat:4` | P0000034/P0000035, base=266500/T before start, 341120/O from start | from-table |
| R-PH-79 | Eligible CA class 7219 in territory 020 uses override factor 1.550 from 2026-01-01 through 2026-09-30. | `InsQuoteEngine>>lookupOverride:into:` (E:107–117) | `tables/overrides.dat:5` | P0000037/P0000038, base=899000/O on end, 754000/T after end | from-table |
| R-PH-80 | GL has an all-states minimum of $500 when no state-specific row applies. | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:3` | P0000062, modified=50000 and minimum yes | from-table |
| R-PH-81 | GL policies in CA have a $750 minimum. | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:4` | P0000061, modified=75000 and minimum yes | from-table |
| R-PH-82 | PR has an all-states minimum of $350 when no state-specific row applies. | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:5` | P0000064, modified=35000 and minimum yes | from-table |
| R-PH-83 | CA has an all-states minimum of $1,000 when no state-specific row applies. | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:6` | P0000121, modified=100000 and minimum yes | from-table |
| R-PH-84 | CA policies in TX have a $1,200 minimum. | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:7` | P0000026/P0000063, modified=120000 and minimum yes | from-table |

## Unused rows

These table values are not active Pharo rules under the loaded gates and fixture dates; keep them visible without counting them as proven.

| ID | Rule in the row | Pharo citation (file:lines) | Table row | Reachability | Status |
| --- | --- | --- | --- | --- | --- |
| R-PH-85 | The GL 91111 row would set a rate of 9.7500 from 2026-01-01. | `InsQuoteEngine>>quote:` (E:28–39), `checkEligibility:into:` (E:69–76), `lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:8`; `tables/line-eligibility.dat:3` | No fixture reaches this; P0000005 declines EX01 first | unproven |
| R-PH-86 | The PR 0567 row would set a rate of 0.4400 from 2026-01-01. | `InsQuoteEngine>>quote:` (E:28–39), `checkEligibility:into:` (E:69–76), `lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:12`; `tables/line-eligibility.dat:4` | No fixture reaches this; P0000009 declines EX02 first | unproven |
| R-PH-87 | The WC 8810 row would set a rate of 0.2500 from 2026-01-01. | `InsQuoteEngine>>quote:` (E:28–39), `validateLine:into:` (E:59–61), `lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:16` | No fixture reaches this; P0000013 rejects LN first | unproven |
| R-PH-88 | PR territory 060 has a factor of 1.400 during 2025 only. | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104); `InsRatingTables>>row:from:inForceOn:` (T:46–53) | `tables/territory-factors.dat:12`; `tables/class-factors.dat:9–12` | No fixture reaches this in force; the PR class rows start in 2026, and P0000023 uses D and factor 1.000 in 2026 | unproven |
| R-PH-89 | The WC all-states minimum row would floor a policy at $250. | `InsQuoteEngine>>quote:` (E:28–39), `validateLine:into:` (E:59–61), `applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:8` | No fixture reaches this; P0000013 rejects LN first | unproven |

## Mutual exclusion and input boundaries

| ID | Rule | Pharo citation (file:lines) | Table row(s) | Executed fixture and result | Status |
| --- | --- | --- | --- | --- | --- |
| R-PH-91 | When several quote gates could fail, the first failure wins in line, exposure, eligibility, class then territory order. | `InsQuoteEngine>>quote:` (E:28–39) | — | No fixture reaches competing simultaneous failures | unproven |
| R-PH-92 | When the premium entering the minimum step exactly equals the selected minimum, the minimum flag remains off. | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:3–7` | No fixture reaches exact equality at this step | unproven |

- Only one gate outcome is final (P0000005 DEC/EX01, P0000013 REJ/LN, P0000001 OK); precedence when two gates could fail is R-PH-91.
- Eligibility and minimum do not combine state and wildcard rows (R-PH-04–06, R-PH-31–32). P0000061/P0000062 distinguish minimum precedence; no fixture reaches simultaneous eligibility matches.
- Class requires the line/class pair (P0000028/P0000030); territory requires the line/territory pair (P0000015/P0000020 show different factors for 010); minimum requires line/state (P0000061/P0000062); override adds class to the line/territory pair (P0000027/P0000031/P0000033). At the end exactly one factor source survives: T (P0000014), D (P0000018) or O (P0000031); no fixture reaches D on CA.
- One of the experience factors 125%, 90% or 100% applies (P0000047/P0000045/P0000046); one deductible factor applies (P0000048–P0000051), not sequential credits. Eligible endorsement charges can add together, subject to the single cap (P0000068/P0000073).
- `InsQuoteScreen>>handle:` and `policyFrom:` (`smalltalk/src/InsRating/InsQuoteScreen.class.st:28–58`) rate only after the form submits a line, trim inputs, uppercase line/state, default omitted territory to 000 and omitted numbers to zero, parse exposure as dollars to cents, and treat checkbox presence as true. These are form mappings rather than separate premium rules; P0000066 exercised the mapped exposure/schedule/multi-policy values, but no fixture reaches missing-field defaults or lowercase line/state in the replay.

## Unresolved legacy ordering difference

All five shared-field disagreements are R-PH-35. The table gives the **displayed modified premium** and minimum flag; the two legacy choices are preserved for the owner rather than choosing one here.

| Fixture | Pharo modified / flagged | COBOL modified / flagged | Observable ordering difference |
| --- | ---: | ---: | --- |
| P0000065 | 40107 / N | 50000 / Y | Credits take an initially above-minimum GL premium below $500. |
| P0000066 | 28263 / Y | 35000 / Y | Schedule and package credits lower the PR premium after Pharo has already raised it to $350. |
| P0000067 | 60000 / Y | 55440 / N | A positive schedule modifier takes the original GL premium above $500, whereas Pharo applies it to $500. |
| P0000082 | 125000 / Y | 100000 / Y | The CA premium is below $1,000 before and after the surcharge on the COBOL path; Pharo applies that surcharge to the $1,000 floor instead. |
| P0000200 | 67500 / Y | 75000 / Y | A negative schedule modifier lowers the GL-in-CA premium after the $750 floor in Pharo. |
