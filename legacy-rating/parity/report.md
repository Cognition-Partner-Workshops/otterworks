# Golden three-way rating parity

Run ID INSR_20261124, expires 2026-12-01. Baseline: `1b421600`. Rule IDs are from the [golden catalog](https://github.com/Cognition-Partner-Workshops/otterworks/pull/3394).

## Executed results

`make insrules-reset` and `make insrules-parity` replayed the same 200 unique fixture IDs through the COBOL batch, the Pharo quote engine, and Java on localhost. The driver compares a keyed SHA-256 for each policy, then reports the differing canonical fields. The original comparison uses status, reason, base, modified, minimum and factor source; it also compares endorsements separately between Pharo and Java. The widened comparison additionally includes billed total on all three pairs. For that comparison, `RATEOUT.cpy:14–15` puts the five-byte fee before the eleven-byte total, so the driver reads total at `r[57:68]`.

Each cell shows **matched / mismatched**, baseline → final. The baseline outputs came from rating code at `1b421600226126008dd2a6a26dd47e391ad18a82` (the widened driver was used for that run). The final outputs came from the rating code committed as `4139296930eca59bb7667febefd6c785899d22a2`.

| Comparison | COBOL ↔ Java | Pharo ↔ Java | COBOL ↔ Pharo |
| --- | ---: | ---: | ---: |
| Widened billed-total comparison | 82 / 118 → 127 / 73 | 113 / 87 → 195 / 5 | 123 / 77 → 123 / 77 |
| Original six-field comparison | 117 / 83 → 200 / 0 | 113 / 87 → 195 / 5 | 195 / 5 → 195 / 5 |

To reproduce the original counts, start from a clean checkout and run these commands from the repository root. Save the baseline outputs outside the checkout before switching commits because the final reset clears `legacy-rating/build`.

```sh
git switch --detach 1b421600226126008dd2a6a26dd47e391ad18a82
make insrules-reset
mkdir -p /home/ubuntu/insrules-golden-baseline
cp legacy-rating/build/cobol.dat legacy-rating/build/pharo.txt legacy-rating/build/java.txt \
  /home/ubuntu/insrules-golden-baseline/

git switch --detach 4139296930eca59bb7667febefd6c785899d22a2
make insrules-reset
```

Run the original driver against the saved baseline outputs, then against the final outputs:

```sh
git show 1b421600226126008dd2a6a26dd47e391ad18a82:legacy-rating/parity/driver.py | python3 - \
  --cobol /home/ubuntu/insrules-golden-baseline/cobol.dat \
  --pharo /home/ubuntu/insrules-golden-baseline/pharo.txt \
  --java /home/ubuntu/insrules-golden-baseline/java.txt \
  --out /home/ubuntu/insrules-golden-baseline/parity-original.json
git show 1b421600226126008dd2a6a26dd47e391ad18a82:legacy-rating/parity/driver.py | python3 - \
  --cobol legacy-rating/build/cobol.dat \
  --pharo legacy-rating/build/pharo.txt \
  --java legacy-rating/build/java.txt \
  --out legacy-rating/build/parity-original.json
```

Each final stack rated 190 policies, declined 7 and rejected 3. Java matches every compared field where the legacy outputs agree. The parity command still reports differences and exits nonzero: the pairwise outcomes below are expected under Legacy's decisions. `mvn -B verify` in the Maven 3.9.9 / Java 21 container passed 25 unit tests and 4 integration tests.

## Mismatch attribution

Counts are per policy, not per field, and use the widened billed-total comparison. A pair gets one primary rule per policy: lookup first, then premium rounding, then the unresolved-at-baseline differences in minimum timing or endorsement-inclusive total. P0000200 has both legacy differences and is counted under R94 for COBOL ↔ Pharo. Counts within each triple are **COBOL/Java, Pharo/Java, COBOL/Pharo**.

Source abbreviations: C = `legacy-rating/cobol/RATEPREM.cbl`; E = `legacy-rating/smalltalk/src/InsRating/InsQuoteEngine.class.st`; T = `legacy-rating/smalltalk/src/InsRating/InsRatingTables.class.st`. Java citations name files in `modern-rating/src/main/java/com/otterworks/rating/service/`; baseline line numbers refer to `1b421600`.

| Rule | Primary cause | COBOL and Pharo source | Java source | Baseline | Final |
| --- | --- | --- | --- | ---: | ---: |
| R15 | Override lookup omitted the policy's requested territory. | C:368–382; E:107–117; `tables/overrides.dat:3–5` | Baseline `RatingTables.java:89–92`; fixed at :89–94, called at `RatingService.java:55`. | 36, 36, 0 | 0, 0, 0 |
| R89 | The last effective day was excluded in class, territory and override lookup. | C:318–335, 338–350, 368–382; T:46–53; E:80–117; `tables/class-factors.dat:5`, `tables/territory-factors.dat:6`, `tables/overrides.dat:3,5` | `RatingTables.java:19–22` | 4, 4, 0 | 0, 0, 0 |
| R90 | Java rounded half-cents to even instead of up. For P0000065, changing the rounding mode restores the $527.73 base premium shared by both legacy stacks. Its modified premium still differs ($500.00 in COBOL and Java versus $401.07 in Pharo) because of minimum timing; see the [R94 table](#r94--apply-the-minimum-after-all-adjustments-cobol). | C:385–386, 398, 413, 423, 428; E:22–25, 120–144, 160–170 | Baseline `RatingService.java:61–68, 142–144`; fixed at :61–66, 140–142. | 5, 5, 0 | 0, 0, 0 |
| R18 | Java did not round to cents between exposure × class rate and the territory factor. | C:384–387; E:120–124 | Baseline `RatingService.java:61, 78`; fixed at :61. | 15, 15, 0 | 0, 0, 0 |
| R46 | A single final rounding lost the effect of rounding after each adjustment (including the sequences in R91 and R92). | C:254–258, 398, 413, 423, 428; E:43–52, 127–144, 160–170 | Baseline `RatingService.java:62–68`; fixed at :62–66. | 23, 23, 0 | 0, 0, 0 |
| R94 | Pharo applies the minimum before schedule and package adjustments; COBOL and Java apply it after all adjustments. | C:254–261, 465–469; E:43–55, 147–157 | `RatingService.java:62–75` | 0, 4, 5 | 0, 5, 5 |
| R100 | COBOL total excludes endorsement charges; Pharo and Java include them. | C:471–473; E:53–55, 173–191 | `RatingService.java:75–77, 123–137` | 35, 0, 72 | 73, 0, 72 |
| **Total** | | | | **118, 87, 77** | **73, 5, 77** |

Policy membership for the baseline shared-rule defects (same in both Java comparisons). The numbers are policy IDs without the leading `P` and zeroes:

- **R15:** 2, 7, 11, 33, 36, 39, 41, 70, 71, 77, 85, 89, 92, 95, 100, 104, 112, 117, 124, 125, 139, 143, 147, 148, 153, 157, 163, 165, 174, 177, 178, 181, 184, 191, 195, 196.
- **R89:** 27, 28, 32, 37. The first two are territory and class boundaries; the last two are override boundaries.
- **R90:** 50, 65, 109, 120, 128. P0000050 rounds a deductible result of $546.345 to $546.35.
- **R18:** 97, 99, 103, 108, 119, 123, 127, 136, 150, 155, 156, 166, 170, 183, 187. Some policies also need later-stage rounding; P0000097 is a witness for R91, and P0000092 (counted under R15) also distinguishes R18.
- **R46:** 76, 91, 105, 107, 110, 111, 129, 130, 132, 142, 152, 159, 162, 164, 168, 173, 179, 180, 182, 188, 189, 193, 198. P0000076 distinguishes R92; on P0000089 (counted under R15), the three stacks now produce $1,610.64 modified.

The baseline COBOL ↔ Java R100 group was 68, 69, 72, 73, 74, 75, 79, 81, 83, 86, 88, 90, 93, 98, 106, 113, 115, 116, 121, 126, 134, 135, 138, 149, 151, 167, 169, 171, 175, 186, 190, 192, 197, 199, 200. The baseline Pharo ↔ Java R94 group was 66, 67, 82, 200; P0000065 was counted under R90 before its shared base rounding was fixed.

## Business decisions (Legacy, 2026-11-24)

### R94 — Apply the minimum after all adjustments (COBOL)

COBOL calls the minimum after schedule, package and wind (C:254–261, 465–469). Pharo applies it after experience and deductible, before schedule and package (E:43–55, 147–157). Java retains the COBOL ordering. **Five golden policies** differ from Pharo:

| Policy | COBOL / Java modified premium and flag | Pharo modified premium and flag |
| --- | ---: | ---: |
| P0000065 | $500.00 / Y | $401.07 / N |
| P0000066 | $350.00 / Y | $282.63 / Y |
| P0000067 | $554.40 / N | $600.00 / Y |
| P0000082 | $1,000.00 / Y | $1,250.00 / Y |
| P0000200 | $750.00 / Y | $675.00 / Y |

### R42–R45, R95–R96, R98–R100 — Keep Pharo's endorsement calculation

COBOL bills modified premium plus the fee (C:471–473). Pharo computes endorsement charges on modified premium and adds them to total (E:53–55, 173–191). Java uses Pharo's eligibility, per-charge rounding and combined cap on the modified premium chosen under R94. On P0000159, both legacy stacks agree on $11,583.29 modified. Pharo rounds the 3% equipment charge from $347.4987 to $347.50, then to $348; baseline Java rounded directly to $347. Java now bills $348, totaling $11,966.29, against COBOL's $11,618.29 without the charge. On P0000200, Pharo's 2% waiver is $14 on $675.00 modified; Java's is $15 on the chosen $750.00. The totals are $724.00 in Pharo, $785.00 in COBOL, and $800.00 in Java.

**73 golden policies** have a charge and differ in total from COBOL after the Java fix. The list is also the 72 policies counted under R100 in the COBOL ↔ Pharo column, plus P0000200 (counted under R94 there):

68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 79, 81, 83, 85, 86, 88, 89, 90, 93, 95, 98, 100, 103, 104, 105, 106, 107, 109, 113, 115, 116, 117, 120, 121, 123, 124, 125, 126, 128, 129, 132, 134, 135, 138, 139, 142, 147, 149, 151, 156, 159, 162, 163, 167, 168, 169, 170, 171, 174, 175, 177, 178, 179, 181, 183, 184, 186, 187, 190, 192, 197, 199, 200.

### R33 — Retain the Florida property wind step (COBOL)

COBOL initializes the factor to 1.000 and uses the last PR/WND row without an effective-date filter before applying the minimum (C:431–443). Pharo has no separate wind step (E:43–55). Java retains the COBOL lookup and rounds the result to cents, half up. **Zero golden policies** move: the shipped `tables/territory-factors.dat:3–15` has no PR/WND row. P0000148 is $3,665.87 modified in all three golden outputs. A separate replay of that policy with temporary PR/WND factors 1.250 and 1.500 (the latter effective in 2027, after the policy date) produced $5,498.81 modified in COBOL and $3,665.87 in Pharo; the Java regression test expects and produces $5,498.81. No shipped table changed.

No other COBOL/Pharo disagreements appeared in the golden replay.
