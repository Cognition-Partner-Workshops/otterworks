# Golden rating parity — INSR_20261124

PR #3396: rating outputs at head `c74073af3` compared with base `aad408aa7`. Both revisions ran `make insrules-reset` locally, including all three batches and `legacy-rating/parity/driver.py`. Each batch output contains exactly the 200 golden fixture IDs.

**No golden policy output changed.** The three raw batch outputs and the driver JSON are byte-for-byte identical between base and head. The 22 GL/18501 input fixtures are all effective in 2026. P0000004 still produces $231.00 base, source T, and $500.00 modified with minimum flag Y in every stack. No fixture reaches the new 1.1500 row effective 2027-01-01 ([R105](../catalog/citations.md#r105)). See the [R51 date contradiction](../catalog/rules.md#class-factor-rows); neither the existing rule nor the table was edited in the refresh.

## Driver results

The counts apply to both revisions. The driver hashes the policy ID with status, reason, base premium, modified premium, minimum flag and factor source; Pharo vs Java additionally compares endorsements. It does not compare fee or total.

| Pair | Policies | Matched | Mismatched |
| --- | ---: | ---: | ---: |
| COBOL vs Java | 200 | 117 | 83 |
| Pharo vs Java | 200 | 113 | 87 |
| COBOL vs Pharo | 200 | 195 | 5 |

COBOL and Pharo each reported 190 OK, 7 DEC and 3 REJ; Java reported 189 OK, 7 DEC and 4 REJ. The driver exited 1 for the mismatches; the reset launcher masks that exit code.

## Mismatch causes

Counts are disjoint within a pair. If multiple fields diverge for one policy, it is counted once: lookup differences first, then minimum timing, then arithmetic (base before modified). Legacy source positions are linked via the catalog. Java source filenames refer to `modern-rating/src/main/java/com/otterworks/rating/service/`.

| Cause | COBOL vs Java | Pharo vs Java | COBOL vs Pharo | Source and executed evidence |
| --- | ---: | ---: | ---: | --- |
| Override omits the requested territory ([R15](../catalog/citations.md#r15)) | 36 | 36 | 0 | Java `RatingService.java:55` and `RatingTables.java:89–92` use only line, class and date; COBOL `RATEPREM.cbl:374` and Pharo `InsQuoteEngine>>lookupOverride:into:` (E:111) require territory. All 36 use a Java O row with a different territory from the fixture; e.g. P0000070 requests 000, but Java uses PR/0702/030 and returns $416.00 base / O instead of $260.00 / T. |
| Exclusive end date ([R89](../catalog/citations.md#r89)) | 4 | 4 | 0 | Java `RatingTables.java:21` excludes the end date; COBOL includes it at `RATEPREM.cbl:325,345,376` and Pharo at `InsRatingTables>>row:from:inForceOn:` (T:52). P0000027 falls back to D on the territory end date; P0000028 rejects with CL on the class end date; P0000032 and P0000037 lose their overrides on the respective end dates. |
| Base premium rounding ([R18](../catalog/citations.md#r18)) | 18 | 17 | 0 | COBOL `RATEPREM.cbl:385–386` and Pharo `InsQuoteEngine>>basePremium:quote:` (E:122–123) round at both base steps; Java `RatingService.java:61,78,142–143` multiplies first and rounds half-even. P0000103 is a base-only difference; P0000065 also rounds $527.725 to $527.73 in COBOL versus $527.72 in Java, but its Pharo/Java mismatch is counted under minimum timing. |
| Adjustment rounding ([R46](../catalog/citations.md#r46)) | 25 | 25 | 0 | COBOL `RATEPREM.cbl:398,413,423,428` and Pharo `InsQuoteEngine>>rate:into:` (E:47–51, with rounding in each adjustment) round by step; Java `RatingService.java:62–68,142–143` rounds half-even only after the product. P0000076 is $4,318.44 modified in both legacy stacks versus $4,318.45 in Java. |
| Minimum timing ([R94](../catalog/citations.md#r94)) | 0 | 5 | 5 | COBOL `RATEPREM.cbl:257–260` and Java `RatingService.java:65–74` floor after schedule and package; Pharo `InsQuoteEngine>>rate:into:` (E:49–51) floors before them. The five policies are P0000065, P0000066, P0000067, P0000082 and P0000200. |
| **Total** | **83** | **87** | **5** | No change from base. |

The quote endorsement differences occur on policies already counted above: 10 under override territory, P0000159 and P0000170 under rounding, and P0000200 under minimum timing. They do not add policy mismatches.

R89 also applies to the changed GL/18501 row: on 2026-12-31 the source predicts a Java CL rejection at class lookup while both legacy lookups still select 1.1000. No golden fixture has that line, class and date; this is a coverage gap, not an observed mismatch.
