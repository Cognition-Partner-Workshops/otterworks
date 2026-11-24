# Three-way rating parity report

All 200 policies in `legacy-rating/fixtures/policies.dat` were run through the COBOL batch (`RATEPREM`), the Pharo quote batch and the Java rating service (`modern-rating/`), then compared by `legacy-rating/parity/driver.py`: a SHA-256 keyed hash per policy over the canonical fields, then field by field on every policy whose hash differs. Rating fields are `status, reason, base, modified, minimum, source`; the Pharo~Java pair also compares `endorsements`. "Before" is the catalog branch as checked out; "after" is this branch. Rule IDs refer to `legacy-rating/catalog/rules.md`.

## Counts

| Pair | Before matched | Before mismatched | After matched | After mismatched |
|---|---|---|---|---|
| cobol~java | 117 | 83 | 200 | 0 |
| pharo~java | 113 | 87 | 195 | 5 |
| cobol~pharo | 195 | 5 | 195 | 5 |

Java batch summary: before `READ=200 OK=189 DEC=7 REJ=4`, after `READ=200 OK=190 DEC=7 REJ=3` (`P0000028` was a false REJ/CL).

## Owner decisions applied

- **R82 minimum order:** COBOL holds. Java applies the minimum after every credit and debit, where `RATEPREM` 3500-MINIMUM-PREMIUM applies it. Java already did this, so no code change; it is now pinned by `appliesTheMinimumAfterScheduleAndMultiPolicy`. The 5 COBOL~Pharo disagreements stay as they are and are the only Pharo~Java differences left.
- **R84 endorsement charges:** keep them. Java adds endorsements to the total the way the Pharo quote screen does (COBOL has no endorsement step, and the COBOL~Java comparison does not include endorsements or total). Pinned by `chargesEndorsementsInTheTotal`.

## Java fixes

Each fix applies where COBOL and Pharo agree. The policies listed for each fix are the baseline mismatches that needed it.

| Fix | Rule | COBOL | Pharo | Java before | Test |
|---|---|---|---|---|---|
| Table rows in force on their end date (4 policies) | R02 | RATEPREM.cbl:324-325, 344-345, 355-356, 375-376 (`<=` / `>=`) | InsRatingTables.class.st:46-52 (both ends inclusive) | RatingTables.java:21 `date.isBefore(to)` (end exclusive) | `classRateIsInForceOnItsEndDate, territoryIsInForceOnItsEndDate, overrideIsInForceOnItsEndDate` |
| Override matched on line, class and territory (36 policies) | R49, R50 | RATEPREM.cbl:372-376 (OT-TERR = POL-TERR, 374) | InsQuoteEngine.class.st:110-112 (`(r at: 3) = aPolicy territory`) | RatingTables.java:89-91; RatingService.java:55 (no territory key) | `overrideMustMatchTheRequestedTerritory` |
| Round exposure x rate to the cent (26 policies) | R54 | RATEPREM.cbl:385 `COMPUTE WS-STEP ROUNDED` | InsQuoteEngine.class.st:122 | RatingService.java:61 (no intermediate rounding) | `roundsExposureTimesRateBeforeTheTerritoryFactor` |
| Round base premium half up (12 policies) | R55 | RATEPREM.cbl:386 `COMPUTE WS-BASE ROUNDED` | InsQuoteEngine.class.st:123 | RatingService.java:61, 143 (HALF_EVEN) | `roundsTheBasePremiumHalfUp` |
| Round after experience mod, half up (7 policies) | R56-R58 | RATEPREM.cbl:398 | InsQuoteEngine.class.st:132 | RatingService.java:62-68 (one rounding, HALF_EVEN) | `roundsEachModifierHalfUpToTheCent` |
| Round after deductible credit, half up (9 policies) | R59-R63 | RATEPREM.cbl:413 | InsQuoteEngine.class.st:143 | RatingService.java:62-68 (one rounding, HALF_EVEN) | `roundsEachModifierHalfUpToTheCent` |
| Round after schedule mod, half up (4 policies) | R64-R66 | RATEPREM.cbl:423 | InsQuoteEngine.class.st:163 | RatingService.java:62-68 (one rounding, HALF_EVEN) | `roundsEachModifierHalfUpToTheCent` |
| Round after multi-policy credit, half up (0 policies) | R67-R69 | RATEPREM.cbl:428 | InsQuoteEngine.class.st:169 | RatingService.java:62-68 (one rounding, HALF_EVEN) | `roundsEachModifierHalfUpToTheCent` |
| Equipment charge rounded to cents before dollars (1 policy) | R89, R90 | n/a (no endorsement step; R84) | InsQuoteEngine.class.st:181 (3% rounded to cents, then whole dollars) | RatingService.java:131 (whole dollars from unrounded 3%) | `roundsTheEquipmentChargeToCentsBeforeDollars` |
| Waiver charge rounded to cents before dollars (0 policies) | R92 | n/a (R84) | InsQuoteEngine.class.st:183 | RatingService.java:134 | `none (no distinguishing fixture)` |
| Endorsement cap rounded half up (0 policies) | R97 | n/a (R84) | InsQuoteEngine.class.st:186 | RatingService.java:139 | `none (no distinguishing fixture)` |

R92, R97 and R67-R69 rounding follow the legacy source too, but no fixture tells them apart from the old Java: the waiver and cap cases were already equal (`P0000170` gives 18093 whether the 18093.25-cent cap is rounded half up or truncated, see R97 in the catalog), and multi-policy rounding was masked by an earlier step. `capsEndorsementsAtAQuarterRoundedHalfUp` pins the `P0000170` output but does not tell the rounding modes apart. These three rules stay unproven against Java until a fixture with a tie exists.

## Every baseline mismatch

Fields show the baseline values in cents. "Rule" is the rule whose Java implementation produced the difference; the citations for each rule are in the table above. Status is the after-state.

| Policy | Pair(s) | Differing fields (before) | Rule | After |
|---|---|---|---|---|
| `P0000002` | cobol~java, pharo~java | cobol~java: base cobol 130200 vs java 195300; modified cobol 130200 vs java 195300; source cobol T vs java O / pharo~java: base pharo 130200 vs java 195300; modified pharo 130200 vs java 195300; source pharo T vs java O | R49, R50 | matched |
| `P0000007` | cobol~java, pharo~java | cobol~java: base cobol 78000 vs java 124800; modified cobol 78000 vs java 124800; source cobol T vs java O / pharo~java: base pharo 78000 vs java 124800; modified pharo 78000 vs java 124800; source pharo T vs java O | R49, R50 | matched |
| `P0000011` | cobol~java, pharo~java | cobol~java: base cobol 435000 vs java 674250; modified cobol 435000 vs java 674250; source cobol T vs java O / pharo~java: base pharo 435000 vs java 674250; modified pharo 435000 vs java 674250; source pharo T vs java O | R49, R50 | matched |
| `P0000027` | cobol~java, pharo~java | cobol~java: base cobol 149400 vs java 124500; modified cobol 149400 vs java 124500; source cobol T vs java D / pharo~java: base pharo 149400 vs java 124500; modified pharo 149400 vs java 124500; source pharo T vs java D | R02 | matched |
| `P0000028` | cobol~java, pharo~java | cobol~java: status cobol OK vs java REJ; reason cobol  vs java CL; base cobol 79800 vs java 0; modified cobol 79800 vs java 0; source cobol T vs java  / pharo~java: status pharo OK vs java REJ; reason pharo  vs java CL; base pharo 79800 vs java 0; modified pharo 79800 vs java 0; source pharo T vs java  | R02 | matched |
| `P0000032` | cobol~java, pharo~java | cobol~java: base cobol 139965 vs java 125968; modified cobol 139965 vs java 125968; source cobol O vs java T / pharo~java: base pharo 139965 vs java 125968; modified pharo 139965 vs java 125968; source pharo O vs java T | R02 | matched |
| `P0000033` | cobol~java, pharo~java | cobol~java: base cobol 102641 vs java 139965; modified cobol 102641 vs java 139965; source cobol T vs java O / pharo~java: base pharo 102641 vs java 139965; modified pharo 102641 vs java 139965; source pharo T vs java O | R49, R50 | matched |
| `P0000036` | cobol~java, pharo~java | cobol~java: base cobol 245180 vs java 341120; modified cobol 245180 vs java 341120; source cobol T vs java O / pharo~java: base pharo 245180 vs java 341120; modified pharo 245180 vs java 341120; source pharo T vs java O | R49, R50 | matched |
| `P0000037` | cobol~java, pharo~java | cobol~java: base cobol 899000 vs java 754000; modified cobol 899000 vs java 754000; source cobol O vs java T / pharo~java: base pharo 899000 vs java 754000; modified pharo 899000 vs java 754000; source pharo O vs java T | R02 | matched |
| `P0000039` | cobol~java, pharo~java | cobol~java: base cobol 493000 vs java 899000; modified cobol 493000 vs java 899000; source cobol T vs java O / pharo~java: base pharo 493000 vs java 899000; modified pharo 493000 vs java 899000; source pharo T vs java O | R49, R50 | matched |
| `P0000041` | cobol~java, pharo~java | cobol~java: base cobol 435000 vs java 674250; modified cobol 435000 vs java 674250; source cobol T vs java O / pharo~java: base pharo 435000 vs java 674250; modified pharo 435000 vs java 674250; source pharo T vs java O | R49, R50 | matched |
| `P0000050` | cobol~java, pharo~java | cobol~java: modified cobol 54635 vs java 54634 / pharo~java: modified pharo 54635 vs java 54634 | R59-R63 | matched |
| `P0000065` | cobol~java, pharo~java, cobol~pharo | cobol~java: base cobol 52773 vs java 52772 / pharo~java: base pharo 52773 vs java 52772; modified pharo 40107 vs java 50000; minimum pharo N vs java Y / cobol~pharo: modified cobol 50000 vs pharo 40107; minimum cobol Y vs pharo N | R55, R82 | open: R82 COBOL~Pharo (Java = COBOL by decision) |
| `P0000066` | pharo~java, cobol~pharo | pharo~java: modified pharo 28263 vs java 35000 / cobol~pharo: modified cobol 35000 vs pharo 28263 | R82 | open: R82 COBOL~Pharo (Java = COBOL by decision) |
| `P0000067` | pharo~java, cobol~pharo | pharo~java: modified pharo 60000 vs java 55440; minimum pharo Y vs java N / cobol~pharo: modified cobol 55440 vs pharo 60000; minimum cobol N vs pharo Y | R82 | open: R82 COBOL~Pharo (Java = COBOL by decision) |
| `P0000070` | cobol~java, pharo~java | cobol~java: base cobol 26000 vs java 41600; modified cobol 35000 vs java 41600; minimum cobol Y vs java N; source cobol T vs java O / pharo~java: base pharo 26000 vs java 41600; modified pharo 35000 vs java 41600; minimum pharo Y vs java N; source pharo T vs java O | R49, R50 | matched |
| `P0000071` | cobol~java, pharo~java | cobol~java: base cobol 416000 vs java 665600; modified cobol 416000 vs java 665600; source cobol T vs java O / pharo~java: base pharo 416000 vs java 665600; modified pharo 416000 vs java 665600; source pharo T vs java O; endorsements pharo 12500 vs java 20000 | R49, R50 | matched |
| `P0000076` | cobol~java, pharo~java | cobol~java: modified cobol 431844 vs java 431845 / pharo~java: modified pharo 431844 vs java 431845 | R64-R66 | matched |
| `P0000077` | cobol~java, pharo~java | cobol~java: base cobol 435000 vs java 674250; modified cobol 413250 vs java 640538; source cobol T vs java O / pharo~java: base pharo 435000 vs java 674250; modified pharo 413250 vs java 640538; source pharo T vs java O; endorsements pharo 8300 vs java 12800 | R49, R50 | matched |
| `P0000082` | pharo~java, cobol~pharo | pharo~java: modified pharo 125000 vs java 100000 / cobol~pharo: modified cobol 100000 vs pharo 125000 | R82 | open: R82 COBOL~Pharo (Java = COBOL by decision) |
| `P0000085` | cobol~java, pharo~java | cobol~java: base cobol 119524 vs java 179285; modified cobol 113548 vs java 170321; source cobol T vs java O / pharo~java: base pharo 119524 vs java 179285; modified pharo 113548 vs java 170321; source pharo T vs java O | R49, R50 | matched |
| `P0000089` | cobol~java, pharo~java | cobol~java: base cobol 195010 vs java 271319; modified cobol 161064 vs java 224090; source cobol T vs java O / pharo~java: base pharo 195010 vs java 271319; modified pharo 161064 vs java 224090; source pharo T vs java O | R49, R50, R59-R63 | matched |
| `P0000091` | cobol~java, pharo~java | cobol~java: modified cobol 65494 vs java 65495 / pharo~java: modified pharo 65494 vs java 65495 | R55 | matched |
| `P0000092` | cobol~java, pharo~java | cobol~java: base cobol 45097 vs java 62744; modified cobol 35473 vs java 49355; source cobol T vs java O / pharo~java: base pharo 45097 vs java 62744; modified pharo 35473 vs java 49355; source pharo T vs java O | R49, R50, R54 | matched |
| `P0000095` | cobol~java, pharo~java | cobol~java: base cobol 1305000 vs java 2022750; modified cobol 1370250 vs java 2123888; source cobol T vs java O / pharo~java: base pharo 1305000 vs java 2022750; modified pharo 1370250 vs java 2123888; source pharo T vs java O; endorsements pharo 27400 vs java 42500 | R49, R50 | matched |
| `P0000097` | cobol~java, pharo~java | cobol~java: base cobol 665082 vs java 665081; modified cobol 956056 vs java 956054 / pharo~java: base pharo 665082 vs java 665081; modified pharo 956056 vs java 956054 | R54, R55, R56-R58 | matched |
| `P0000099` | cobol~java, pharo~java | cobol~java: base cobol 592244 vs java 592245; modified cobol 592244 vs java 592245 / pharo~java: base pharo 592244 vs java 592245; modified pharo 592244 vs java 592245 | R54 | matched |
| `P0000100` | cobol~java, pharo~java | cobol~java: base cobol 699961 vs java 1049942; modified cobol 748083 vs java 1122126; source cobol D vs java O / pharo~java: base pharo 699961 vs java 1049942; modified pharo 748083 vs java 1122126; source pharo D vs java O | R49, R50 | matched |
| `P0000103` | cobol~java, pharo~java | cobol~java: base cobol 68249 vs java 68250 / pharo~java: base pharo 68249 vs java 68250 | R54 | matched |
| `P0000104` | cobol~java, pharo~java | cobol~java: base cobol 618986 vs java 977346; modified cobol 773733 vs java 1221683; source cobol T vs java O / pharo~java: base pharo 618986 vs java 977346; modified pharo 773733 vs java 1221683; source pharo T vs java O | R49, R50 | matched |
| `P0000105` | cobol~java, pharo~java | cobol~java: modified cobol 224208 vs java 224207 / pharo~java: modified pharo 224208 vs java 224207 | R59-R63 | matched |
| `P0000107` | cobol~java, pharo~java | cobol~java: modified cobol 267958 vs java 267957 / pharo~java: modified pharo 267958 vs java 267957 | R56-R58 | matched |
| `P0000108` | cobol~java, pharo~java | cobol~java: base cobol 711507 vs java 711506 / pharo~java: base pharo 711507 vs java 711506 | R54, R59-R63 | matched |
| `P0000109` | cobol~java, pharo~java | cobol~java: modified cobol 237173 vs java 237172 / pharo~java: modified pharo 237173 vs java 237172 | R56-R58 | matched |
| `P0000110` | cobol~java, pharo~java | cobol~java: modified cobol 176805 vs java 176806 / pharo~java: modified pharo 176805 vs java 176806 | R54 | matched |
| `P0000111` | cobol~java, pharo~java | cobol~java: modified cobol 958198 vs java 958197 / pharo~java: modified pharo 958198 vs java 958197 | R55 | matched |
| `P0000112` | cobol~java, pharo~java | cobol~java: base cobol 62099 vs java 110398; modified cobol 60857 vs java 108190; source cobol T vs java O / pharo~java: base pharo 62099 vs java 110398; modified pharo 60857 vs java 108190; source pharo T vs java O | R49, R50 | matched |
| `P0000117` | cobol~java, pharo~java | cobol~java: base cobol 1160000 vs java 1798000; modified cobol 1250480 vs java 1938244; source cobol T vs java O / pharo~java: base pharo 1160000 vs java 1798000; modified pharo 1250480 vs java 1938244; source pharo T vs java O; endorsements pharo 25000 vs java 38800 | R49, R50 | matched |
| `P0000119` | cobol~java, pharo~java | cobol~java: base cobol 348644 vs java 348645; modified cobol 400940 vs java 400941 / pharo~java: base pharo 348644 vs java 348645; modified pharo 400940 vs java 400941 | R54, R59-R63 | matched |
| `P0000120` | cobol~java, pharo~java | cobol~java: base cobol 577517 vs java 577516 / pharo~java: base pharo 577517 vs java 577516 | R54 | matched |
| `P0000123` | cobol~java, pharo~java | cobol~java: base cobol 296281 vs java 296282 / pharo~java: base pharo 296281 vs java 296282 | R54 | matched |
| `P0000124` | cobol~java, pharo~java | cobol~java: base cobol 812684 vs java 1219025; modified cobol 694845 vs java 1042267; source cobol D vs java O / pharo~java: base pharo 812684 vs java 1219025; modified pharo 694845 vs java 1042267; source pharo D vs java O; endorsements pharo 40900 vs java 47800 | R49, R50 | matched |
| `P0000125` | cobol~java, pharo~java | cobol~java: base cobol 801050 vs java 1092341; modified cobol 1001313 vs java 1365426; source cobol T vs java O / pharo~java: base pharo 801050 vs java 1092341; modified pharo 1001313 vs java 1365426; source pharo T vs java O; endorsements pharo 20000 vs java 27300 | R49, R50, R55 | matched |
| `P0000127` | cobol~java, pharo~java | cobol~java: base cobol 800662 vs java 800663 / pharo~java: base pharo 800662 vs java 800663 | R54 | matched |
| `P0000128` | cobol~java, pharo~java | cobol~java: base cobol 286979 vs java 286978 / pharo~java: base pharo 286979 vs java 286978 | R54 | matched |
| `P0000129` | cobol~java, pharo~java | cobol~java: modified cobol 807913 vs java 807914 / pharo~java: modified pharo 807913 vs java 807914 | R55 | matched |
| `P0000130` | cobol~java, pharo~java | cobol~java: modified cobol 265377 vs java 265376 / pharo~java: modified pharo 265377 vs java 265376 | R56-R58 | matched |
| `P0000132` | cobol~java, pharo~java | cobol~java: modified cobol 358707 vs java 358706 / pharo~java: modified pharo 358707 vs java 358706 | R54 | matched |
| `P0000136` | cobol~java, pharo~java | cobol~java: base cobol 401272 vs java 401271 / pharo~java: base pharo 401272 vs java 401271 | R54 | matched |
| `P0000139` | cobol~java, pharo~java | cobol~java: base cobol 1141544 vs java 1712316; modified cobol 1027390 vs java 1541084; source cobol T vs java O / pharo~java: base pharo 1141544 vs java 1712316; modified pharo 1027390 vs java 1541084; source pharo T vs java O | R49, R50 | matched |
| `P0000142` | cobol~java, pharo~java | cobol~java: modified cobol 950894 vs java 950893 / pharo~java: modified pharo 950894 vs java 950893 | R55 | matched |
| `P0000143` | cobol~java, pharo~java | cobol~java: base cobol 274853 vs java 488627; modified cobol 204821 vs java 364125; source cobol T vs java O / pharo~java: base pharo 274853 vs java 488627; modified pharo 204821 vs java 364125; source pharo T vs java O | R49, R50, R56-R58 | matched |
| `P0000147` | cobol~java, pharo~java | cobol~java: base cobol 637056 vs java 868713; modified cobol 573350 vs java 781842; source cobol T vs java O / pharo~java: base pharo 637056 vs java 868713; modified pharo 573350 vs java 781842; source pharo T vs java O | R49, R50, R55 | matched |
| `P0000148` | cobol~java, pharo~java | cobol~java: base cobol 366587 vs java 586539; modified cobol 366587 vs java 586539; source cobol D vs java O / pharo~java: base pharo 366587 vs java 586539; modified pharo 366587 vs java 586539; source pharo D vs java O | R49, R50 | matched |
| `P0000150` | cobol~java, pharo~java | cobol~java: base cobol 285451 vs java 285452 / pharo~java: base pharo 285451 vs java 285452 | R54 | matched |
| `P0000152` | cobol~java, pharo~java | cobol~java: modified cobol 889342 vs java 889341 / pharo~java: modified pharo 889342 vs java 889341 | R59-R63, R64-R66 | matched |
| `P0000153` | cobol~java, pharo~java | cobol~java: base cobol 497455 vs java 884365; modified cobol 457659 vs java 813616; source cobol T vs java O / pharo~java: base pharo 497455 vs java 884365; modified pharo 457659 vs java 813616; source pharo T vs java O | R49, R50 | matched |
| `P0000155` | cobol~java, pharo~java | cobol~java: base cobol 265379 vs java 265378; modified cobol 304423 vs java 304422 / pharo~java: base pharo 265379 vs java 265378; modified pharo 304423 vs java 304422 | R54, R55 | matched |
| `P0000156` | cobol~java, pharo~java | cobol~java: base cobol 220202 vs java 220203; modified cobol 188795 vs java 188796 / pharo~java: base pharo 220202 vs java 220203; modified pharo 188795 vs java 188796 | R54, R64-R66 | matched |
| `P0000157` | cobol~java, pharo~java | cobol~java: base cobol 1885000 vs java 2921750; modified cobol 2384525 vs java 3696014; source cobol T vs java O / pharo~java: base pharo 1885000 vs java 2921750; modified pharo 2384525 vs java 3696014; source pharo T vs java O | R49, R50 | matched |
| `P0000159` | cobol~java, pharo~java | cobol~java: modified cobol 1158329 vs java 1158328 / pharo~java: modified pharo 1158329 vs java 1158328; endorsements pharo 34800 vs java 34700 | R89, R90 | matched |
| `P0000162` | cobol~java, pharo~java | cobol~java: modified cobol 194130 vs java 194129 / pharo~java: modified pharo 194130 vs java 194129 | R55 | matched |
| `P0000163` | cobol~java, pharo~java | cobol~java: base cobol 290000 vs java 449500; modified cobol 319000 vs java 494450; source cobol T vs java O / pharo~java: base pharo 290000 vs java 449500; modified pharo 319000 vs java 494450; source pharo T vs java O; endorsements pharo 6400 vs java 9900 | R49, R50 | matched |
| `P0000164` | cobol~java, pharo~java | cobol~java: modified cobol 380454 vs java 380453 / pharo~java: modified pharo 380454 vs java 380453 | R59-R63 | matched |
| `P0000165` | cobol~java, pharo~java | cobol~java: base cobol 437981 vs java 778631; modified cobol 350385 vs java 622905; source cobol T vs java O / pharo~java: base pharo 437981 vs java 778631; modified pharo 350385 vs java 622905; source pharo T vs java O | R49, R50, R54, R55 | matched |
| `P0000166` | cobol~java, pharo~java | cobol~java: base cobol 322855 vs java 322856; modified cobol 291376 vs java 291377 / pharo~java: base pharo 322855 vs java 322856; modified pharo 291376 vs java 291377 | R54, R59-R63 | matched |
| `P0000168` | cobol~java, pharo~java | cobol~java: modified cobol 990774 vs java 990773 / pharo~java: modified pharo 990774 vs java 990773 | R54 | matched |
| `P0000170` | cobol~java, pharo~java | cobol~java: base cobol 80192 vs java 80193; modified cobol 72373 vs java 72374 / pharo~java: base pharo 80192 vs java 80193; modified pharo 72373 vs java 72374; endorsements pharo 18093 vs java 18094 | R54 | matched |
| `P0000173` | cobol~java, pharo~java | cobol~java: modified cobol 73765 vs java 73766 / pharo~java: modified pharo 73765 vs java 73766 | R59-R63 | matched |
| `P0000174` | cobol~java, pharo~java | cobol~java: base cobol 174699 vs java 310576; modified cobol 182976 vs java 325289; source cobol T vs java O / pharo~java: base pharo 174699 vs java 310576; modified pharo 182976 vs java 325289; source pharo T vs java O; endorsements pharo 7500 vs java 9800 | R49, R50, R56-R58 | matched |
| `P0000177` | cobol~java, pharo~java | cobol~java: base cobol 547336 vs java 821004; modified cobol 684170 vs java 1026255; source cobol T vs java O / pharo~java: base pharo 547336 vs java 821004; modified pharo 684170 vs java 1026255; source pharo T vs java O; endorsements pharo 25700 vs java 32500 | R49, R50 | matched |
| `P0000178` | cobol~java, pharo~java | cobol~java: base cobol 778980 vs java 1168471; modified cobol 560866 vs java 841299; source cobol D vs java O / pharo~java: base pharo 778980 vs java 1168471; modified pharo 560866 vs java 841299; source pharo D vs java O | R49, R50 | matched |
| `P0000179` | cobol~java, pharo~java | cobol~java: modified cobol 135602 vs java 135603 / pharo~java: modified pharo 135602 vs java 135603 | R55 | matched |
| `P0000180` | cobol~java, pharo~java | cobol~java: modified cobol 51370 vs java 51371 / pharo~java: modified pharo 51370 vs java 51371 | R54 | matched |
| `P0000181` | cobol~java, pharo~java | cobol~java: base cobol 1740000 vs java 2697000; modified cobol 2175000 vs java 3371250; source cobol T vs java O / pharo~java: base pharo 1740000 vs java 2697000; modified pharo 2175000 vs java 3371250; source pharo T vs java O; endorsements pharo 43500 vs java 67400 | R49, R50 | matched |
| `P0000182` | cobol~java, pharo~java | cobol~java: modified cobol 1209568 vs java 1209567 / pharo~java: modified pharo 1209568 vs java 1209567 | R64-R66 | matched |
| `P0000183` | cobol~java, pharo~java | cobol~java: base cobol 283317 vs java 283318 / pharo~java: base pharo 283317 vs java 283318 | R54 | matched |
| `P0000184` | cobol~java, pharo~java | cobol~java: base cobol 510781 vs java 766171; modified cobol 510781 vs java 766171; source cobol D vs java O / pharo~java: base pharo 510781 vs java 766171; modified pharo 510781 vs java 766171; source pharo D vs java O | R49, R50 | matched |
| `P0000187` | cobol~java, pharo~java | cobol~java: base cobol 321979 vs java 321980; modified cobol 257583 vs java 257584 / pharo~java: base pharo 321979 vs java 321980; modified pharo 257583 vs java 257584 | R54 | matched |
| `P0000188` | cobol~java, pharo~java | cobol~java: modified cobol 1257355 vs java 1257354 / pharo~java: modified pharo 1257355 vs java 1257354 | R54 | matched |
| `P0000189` | cobol~java, pharo~java | cobol~java: modified cobol 649788 vs java 649787 / pharo~java: modified pharo 649788 vs java 649787 | R56-R58 | matched |
| `P0000191` | cobol~java, pharo~java | cobol~java: base cobol 242301 vs java 387682; modified cobol 302876 vs java 484603; source cobol D vs java O / pharo~java: base pharo 242301 vs java 387682; modified pharo 302876 vs java 484603; source pharo D vs java O | R49, R50 | matched |
| `P0000193` | cobol~java, pharo~java | cobol~java: modified cobol 122705 vs java 122704 / pharo~java: modified pharo 122705 vs java 122704 | R54 | matched |
| `P0000195` | cobol~java, pharo~java | cobol~java: base cobol 621202 vs java 864282; modified cobol 416404 vs java 579345; source cobol T vs java O / pharo~java: base pharo 621202 vs java 864282; modified pharo 416404 vs java 579345; source pharo T vs java O | R49, R50 | matched |
| `P0000196` | cobol~java, pharo~java | cobol~java: base cobol 125060 vs java 200096; modified cobol 118807 vs java 190091; source cobol T vs java O / pharo~java: base pharo 125060 vs java 200096; modified pharo 118807 vs java 190091; source pharo T vs java O | R49, R50 | matched |
| `P0000198` | cobol~java, pharo~java | cobol~java: modified cobol 106154 vs java 106155 / pharo~java: modified pharo 106154 vs java 106155 | R54 | matched |
| `P0000200` | pharo~java, cobol~pharo | pharo~java: modified pharo 67500 vs java 75000; endorsements pharo 1400 vs java 1500 / cobol~pharo: modified cobol 75000 vs pharo 67500 | R82 | open: R82 COBOL~Pharo (Java = COBOL by decision) |

## Endorsement charges (R84) and the totals

The parity counts do not show R84, because `total` is not a canonical field. The driver compares COBOL with the other two stacks on the rating fields only (`status, reason, base, modified, minimum, source`), and adds `endorsements` only for Pharo~Java. No pair compares `total`. The executed output for all 200 fixtures (`legacy-rating/build/`, read with `driver.py`) shows:

| Check on the executed output | Result |
|---|---|
| Fixtures with an endorsement charge (Pharo and Java) | 73 (for example `P0000071`: endorsements 12500, total 432000) |
| COBOL total = modified + fee (R83, R84) | all 190 OK policies (`P0000071`: 416000 + 3500 = 419500) |
| Pharo and Java total = modified + endorsements + fee | all OK policies |
| COBOL total differs from Java total | 73 policies: exactly the 73 with an endorsement charge |
| COBOL total differs from Pharo total | 77 policies: the 73 with an endorsement charge, plus 4 R82 policies without one |
| Pharo total differs from Java total | 5 policies, all R82 |

So Java charges endorsements the way Pharo does, as the owner decided. On the totals, Java follows Pharo and differs from COBOL on every endorsed fixture. That difference is intended and not counted. On each of the 73 endorsed fixtures, Java total = COBOL total + endorsements. On the other 127, the two totals are equal.

This PR also fixes how `read_cobol` in `driver.py` reads the COBOL total. It sliced `r[56:67]` instead of `r[57:68]` (0-based): `OUT-FEE` in `RATEOUT.cpy` takes offsets 52-56, so `OUT-TOTAL` starts at 57. The old reading gave totals a factor of 10 too small (`P0000071`: 41950 instead of 419500). No comparison used `total`, so the counts do not change. The figures above come from the corrected reader.

## Left open

| Policy | COBOL~Pharo difference | Rule | COBOL | Pharo |
|---|---|---|---|---|
| `P0000065` | modified cobol 50000 vs pharo 40107; minimum cobol Y vs pharo N | R82 | RATEPREM.cbl:252-262 (3500 after 3300/3400), 465-469 | InsQuoteEngine.class.st:45-51, 147-157 (minimum before schedule and multi-policy) |
| `P0000066` | modified cobol 35000 vs pharo 28263 | R82 | RATEPREM.cbl:252-262 (3500 after 3300/3400), 465-469 | InsQuoteEngine.class.st:45-51, 147-157 (minimum before schedule and multi-policy) |
| `P0000067` | modified cobol 55440 vs pharo 60000; minimum cobol N vs pharo Y | R82 | RATEPREM.cbl:252-262 (3500 after 3300/3400), 465-469 | InsQuoteEngine.class.st:45-51, 147-157 (minimum before schedule and multi-policy) |
| `P0000082` | modified cobol 100000 vs pharo 125000 | R82 | RATEPREM.cbl:252-262 (3500 after 3300/3400), 465-469 | InsQuoteEngine.class.st:45-51, 147-157 (minimum before schedule and multi-policy) |
| `P0000200` | modified cobol 75000 vs pharo 67500 | R82 | RATEPREM.cbl:252-262 (3500 after 3300/3400), 465-469 | InsQuoteEngine.class.st:45-51, 147-157 (minimum before schedule and multi-policy) |

The 5 remaining Pharo~Java differences are the same policies: Java follows COBOL by the R82 decision. On `P0000200` the endorsement amount also differs (Pharo 1400, Java 1500) because the 2% waiver is taken on the modified premium, which R82 changes; the endorsement rule itself matches.

No new COBOL~Pharo disagreement was found: the COBOL~Pharo pair is 195/5 before and after, and all 5 are R82. Legacy code and tables were not changed.

## Reproduce

Both targets exit nonzero while any pair has a mismatch, so they currently fail on the 5 accepted R82 differences; the counts are in the `PARITY` lines and `parity.json`.

```
make insrules-reset     # resets the estate, runs COBOL, Pharo and Java on all 200 fixtures, then parity
make insrules-parity    # reruns all three raters (insrules-run), then compares; writes legacy-rating/build/parity.json
```
