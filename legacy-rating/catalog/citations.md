# Golden rule citations

Sources and line numbers are from `1b421600` and are relative to `legacy-rating/`. COBOL paths in the table are relative to `cobol/`. A dash means no applicable row/citation. “No step” cites the complete dispatch path, not an equivalent method.

- E = `smalltalk/src/InsRating/InsQuoteEngine.class.st`.
- T = `smalltalk/src/InsRating/InsRatingTables.class.st`.
- Q = `smalltalk/src/InsRating/InsQuote.class.st`.

The source ID is the stable join to [rules.md](rules.md).

| ID | COBOL paragraph or copybook | Pharo class and selector | Data rows |
| --- | --- | --- | --- |
| <a id="r01"></a>R01 | `RATEPREM.cbl:1100-VALIDATE-LINE L276-L281` | `InsQuoteEngine>>validateLine:into:` (E:59–61) | — |
| <a id="r02"></a>R02 | `RATEPREM.cbl:1200-VALIDATE-EXPOSURE L283-L287` | `InsQuoteEngine>>validateExposure:into:` (E:64–66) | — |
| <a id="r03"></a>R03 | `RATEPREM.cbl:1000-RATE-POLICY L239-L262` | `InsQuoteEngine>>quote:` (E:28–39) | — |
| <a id="r04"></a>R04 | `RATEPREM.cbl:1000-RATE-POLICY L231-L262` | `InsQuoteEngine>>quote:` (E:28–39); `InsQuote>>initialize` (Q:13–17) | — |
| <a id="r05"></a>R05 | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY L291-L310` | `InsQuoteEngine>>checkEligibility:into:` (E:69–76) | `tables/line-eligibility.dat:5` |
| <a id="r06"></a>R06 | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY L291-L310` | `InsQuoteEngine>>checkEligibility:into:` (E:69–76) | `tables/line-eligibility.dat:3`; `tables/line-eligibility.dat:4`; `tables/line-eligibility.dat:6` |
| <a id="r07"></a>R07 | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY L291-L310` | `InsQuoteEngine>>checkEligibility:into:` (E:69–76) | `tables/line-eligibility.dat:5` |
| <a id="r08"></a>R08 | `RATEPREM.cbl:2010-APPLY-ELIGIBILITY L312-L316` | `InsQuoteEngine>>checkEligibility:into:` (E:69–77) | `tables/line-eligibility.dat:3`; `tables/line-eligibility.dat:4`; `tables/line-eligibility.dat:5` |
| <a id="r09"></a>R09 | `RATEPREM.cbl:2010-APPLY-ELIGIBILITY L312-L316` | `InsQuoteEngine>>checkEligibility:into:` (E:69–76) | `tables/line-eligibility.dat:6` |
| <a id="r10"></a>R10 | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335` | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:5`; `tables/class-factors.dat:6` |
| <a id="r11"></a>R11 | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335` | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:3` |
| <a id="r12"></a>R12 | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350` | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:6`; `tables/territory-factors.dat:7` |
| <a id="r13"></a>R13 | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L361` | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:3`; `tables/territory-factors.dat:8`; `tables/territory-factors.dat:12` |
| <a id="r14"></a>R14 | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L365`; `RATEPREM.cbl:1000-RATE-POLICY L249-L254` | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:3`; `tables/territory-factors.dat:8`; `tables/territory-factors.dat:13` |
| <a id="r15"></a>R15 | `RATEPREM.cbl:2300-LOOKUP-OVERRIDE L367-L382` | `InsQuoteEngine>>lookupOverride:into:` (E:107–117) | `tables/overrides.dat:3`; `tables/overrides.dat:4`; `tables/overrides.dat:5`; `tables/territory-factors.dat:6`; `tables/territory-factors.dat:7` |
| <a id="r16"></a>R16 | `RATEPREM.cbl:2300-LOOKUP-OVERRIDE L368-L382` | `InsQuoteEngine>>lookupOverride:into:` (E:107–117) | `tables/overrides.dat:3`; `tables/overrides.dat:4`; `tables/overrides.dat:5` |
| <a id="r17"></a>R17 | `RATEPREM.cbl:0130-OPEN-END-DATE L223-L229`; `RATEPREM.cbl:0100-LOAD-TABLES L109-L189` | `InsRatingTables>>row:from:inForceOn:` (T:46–53); `InsQuoteEngine>>lookupClassRate:into:` (E:80–87), `InsQuoteEngine>>lookupTerritory:into:` (E:90–104), `InsQuoteEngine>>lookupOverride:into:` (E:107–117) | `tables/class-factors.dat:6`; `tables/territory-factors.dat:7`; `tables/overrides.dat:4` |
| <a id="r18"></a>R18 | `RATEPREM.cbl:3000-BASE-PREMIUM L384-L387` | `InsQuoteEngine>>basePremium:quote:` (E:120–124); `InsQuoteEngine>>lookupClassRate:into:` (E:80–87), `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/class-factors.dat:10`; `tables/territory-factors.dat:11` |
| <a id="r19"></a>R19 | `RATEPREM.cbl:3100-EXPERIENCE-MOD L389-L398` | `InsQuoteEngine>>experienceMod:premium:` (E:127–133); `InsQuoteScreen>>pageFor:quote:` (`InsQuoteScreen>>smalltalk/src/InsRating/InsQuoteScreen.class.st:83`) | — |
| <a id="r20"></a>R20 | `RATEPREM.cbl:3100-EXPERIENCE-MOD L389-L398` | `InsQuoteEngine>>experienceMod:premium:` (E:127–133) | — |
| <a id="r21"></a>R21 | `RATEPREM.cbl:3100-EXPERIENCE-MOD L389-L398` | `InsQuoteEngine>>experienceMod:premium:` (E:127–133) | — |
| <a id="r22"></a>R22 | `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT L401-L413` | `InsQuoteEngine>>deductibleCredit:premium:` (E:136–144) | — |
| <a id="r23"></a>R23 | `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT L401-L413` | `InsQuoteEngine>>deductibleCredit:premium:` (E:136–144) | — |
| <a id="r24"></a>R24 | `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT L401-L413` | `InsQuoteEngine>>deductibleCredit:premium:` (E:136–144) | — |
| <a id="r25"></a>R25 | `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT L401-L413` | `InsQuoteEngine>>deductibleCredit:premium:` (E:136–144) | — |
| <a id="r26"></a>R26 | `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT L400-L413` | `InsQuoteEngine>>deductibleCredit:premium:` (E:136–144) | — |
| <a id="r27"></a>R27 | `RATEPREM.cbl:3300-SCHEDULE-MOD L415-L423` | `InsQuoteEngine>>scheduleMod:premium:` (E:160–164) | — |
| <a id="r28"></a>R28 | `RATEPREM.cbl:3300-SCHEDULE-MOD L415-L423` | `InsQuoteEngine>>scheduleMod:premium:` (E:160–164) | — |
| <a id="r29"></a>R29 | `RATEPREM.cbl:3300-SCHEDULE-MOD L415-L423` | `InsQuoteEngine>>scheduleMod:premium:` (E:160–164) | — |
| <a id="r30"></a>R30 | `RATEPREM.cbl:3400-MULTI-POLICY L425-L429` | `InsQuoteEngine>>multiPolicy:premium:` (E:167–170) | — |
| <a id="r31"></a>R31 | `RATEPREM.cbl:3400-MULTI-POLICY L425-L429` | `InsQuoteEngine>>multiPolicy:premium:` (E:167–170) | — |
| <a id="r32"></a>R32 | `RATEPREM.cbl:3400-MULTI-POLICY L425-L429` | `InsQuoteEngine>>multiPolicy:premium:` (E:167–170) | — |
| <a id="r33"></a>R33 | `RATEPREM.cbl:3450-WIND-SURCHARGE L431-L443` | `InsQuoteEngine>>rate:into:` (E:43–55; no wind step) | `tables/territory-factors.dat:3-15` |
| <a id="r34"></a>R34 | `RATEPREM.cbl:3450-WIND-SURCHARGE L433-L443` | `InsQuoteEngine>>rate:into:` (E:43–55; no wind step) | `tables/territory-factors.dat:3-15` |
| <a id="r35"></a>R35 | `RATEPREM.cbl:3450-WIND-SURCHARGE L433-L443` | `InsQuoteEngine>>rate:into:` (E:43–55; no wind step) | `tables/territory-factors.dat:3-15` |
| <a id="r36"></a>R36 | `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L464` | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:3`; `tables/minimum-premium.dat:4`; `tables/minimum-premium.dat:6`; `tables/minimum-premium.dat:7` |
| <a id="r37"></a>R37 | `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L464` | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:3`; `tables/minimum-premium.dat:5`; `tables/minimum-premium.dat:6` |
| <a id="r38"></a>R38 | `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L469` | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:3`; `tables/minimum-premium.dat:5`; `tables/minimum-premium.dat:6` |
| <a id="r39"></a>R39 | `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L469` | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:3`; `tables/minimum-premium.dat:5` |
| <a id="r40"></a>R40 | `RATEPREM.cbl:1000-RATE-POLICY L235-L238`; `RATEPREM.cbl:3500-MINIMUM-PREMIUM L465-L469` | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:3` |
| <a id="r41"></a>R41 | `RATEPREM.cbl:WORKING-STORAGE SECTION L75-L75`; `RATEPREM.cbl:1000-RATE-POLICY L253-L262`; `RATEPREM.cbl:3600-POLICY-FEE L471-L473` | `InsQuoteEngine>>rate:into:` (E:43–55), `InsQuoteEngine>>policyFee` (E:195) | — |
| <a id="r42"></a>R42 | `copybooks/POLREC.cpy L16-L16`; `RATEPREM.cbl:1000-RATE-POLICY L231-L262` | `InsQuoteEngine>>endorsements:premium:` (E:178–179) | — |
| <a id="r43"></a>R43 | `copybooks/POLREC.cpy L17-L17`; `RATEPREM.cbl:1000-RATE-POLICY L231-L262` | `InsQuoteEngine>>endorsements:premium:` (E:180–181); `InsQuoteEngine>>wholeDollars:` (E:190–192) | — |
| <a id="r44"></a>R44 | `copybooks/POLREC.cpy L18-L18`; `RATEPREM.cbl:1000-RATE-POLICY L231-L262` | `InsQuoteEngine>>endorsements:premium:` (E:182–183); `InsQuoteEngine>>wholeDollars:` (E:190–192) | — |
| <a id="r45"></a>R45 | `copybooks/POLREC.cpy L19-L19`; `RATEPREM.cbl:1000-RATE-POLICY L231-L262` | `InsQuoteEngine>>endorsements:premium:` (E:184–185) | — |
| <a id="r46"></a>R46 | `RATEPREM.cbl:1000-RATE-POLICY L253-L261`; `RATEPREM.cbl:3100-EXPERIENCE-MOD L389-L398`; `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT L401-L413`; `RATEPREM.cbl:3300-SCHEDULE-MOD L415-L423`; `RATEPREM.cbl:3400-MULTI-POLICY L425-L429` | `InsQuoteEngine>>rate:into:` (E:43–55); `InsQuoteEngine>>round:scale:` (E:22–25) | — |
| <a id="r47"></a>R47 | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335` | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:3` |
| <a id="r48"></a>R48 | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335` | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:4` |
| <a id="r49"></a>R49 | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335` | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:5` |
| <a id="r50"></a>R50 | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335` | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:6` |
| <a id="r51"></a>R51 | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335` | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:7` |
| <a id="r52"></a>R52 | `RATEPREM.cbl:1000-RATE-POLICY L243-L248`; `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335` | `InsQuoteEngine>>quote:` (E:28–39), `InsQuoteEngine>>checkEligibility:into:` (E:69–76), `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:8`; `tables/line-eligibility.dat:3` |
| <a id="r53"></a>R53 | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335` | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:9` |
| <a id="r54"></a>R54 | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335` | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:10` |
| <a id="r55"></a>R55 | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335` | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:11` |
| <a id="r56"></a>R56 | `RATEPREM.cbl:1000-RATE-POLICY L243-L248`; `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335` | `InsQuoteEngine>>quote:` (E:28–39), `InsQuoteEngine>>checkEligibility:into:` (E:69–76), `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:12`; `tables/line-eligibility.dat:4` |
| <a id="r57"></a>R57 | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335` | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:13` |
| <a id="r58"></a>R58 | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335` | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:14`; `tables/line-eligibility.dat:5` |
| <a id="r59"></a>R59 | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335` | `InsQuoteEngine>>lookupClassRate:into:` (E:80–87) | `tables/class-factors.dat:15` |
| <a id="r60"></a>R60 | `RATEPREM.cbl:1000-RATE-POLICY L239-L248`; `RATEPREM.cbl:1100-VALIDATE-LINE L276-L281`; `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335` | `InsQuoteEngine>>quote:` (E:28–39), `InsQuoteEngine>>validateLine:into:` (E:59–61), `InsQuoteEngine>>lookupClassRate:into:` (E:80–87); `InsQuoteEngine>>validateLine:into:` (E:59–61); `InsQuoteEngine>>quote:` (E:28–39) | `tables/class-factors.dat:16` |
| <a id="r61"></a>R61 | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY L291-L310`; `RATEPREM.cbl:2010-APPLY-ELIGIBILITY L312-L316` | `InsQuoteEngine>>checkEligibility:into:` (E:69–76) | `tables/line-eligibility.dat:3` |
| <a id="r62"></a>R62 | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY L291-L310`; `RATEPREM.cbl:2010-APPLY-ELIGIBILITY L312-L316` | `InsQuoteEngine>>checkEligibility:into:` (E:69–76) | `tables/line-eligibility.dat:4` |
| <a id="r63"></a>R63 | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY L291-L310`; `RATEPREM.cbl:2010-APPLY-ELIGIBILITY L312-L316` | `InsQuoteEngine>>checkEligibility:into:` (E:69–76) | `tables/line-eligibility.dat:5` |
| <a id="r64"></a>R64 | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY L291-L310`; `RATEPREM.cbl:2010-APPLY-ELIGIBILITY L312-L316` | `InsQuoteEngine>>checkEligibility:into:` (E:69–76) | `tables/line-eligibility.dat:6` |
| <a id="r65"></a>R65 | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L361` | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:3` |
| <a id="r66"></a>R66 | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350` | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:4` |
| <a id="r67"></a>R67 | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350` | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:5` |
| <a id="r68"></a>R68 | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350` | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:6` |
| <a id="r69"></a>R69 | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350` | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:7` |
| <a id="r70"></a>R70 | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L361` | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:8` |
| <a id="r71"></a>R71 | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350` | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:9` |
| <a id="r72"></a>R72 | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350` | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:10` |
| <a id="r73"></a>R73 | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350` | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:11` |
| <a id="r74"></a>R74 | `RATEPREM.cbl:1000-RATE-POLICY L246-L251`; `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L361` | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104); `InsRatingTables>>row:from:inForceOn:` (T:46–53) | `tables/territory-factors.dat:12`; `tables/class-factors.dat:9-12` |
| <a id="r75"></a>R75 | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L361` | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:13` |
| <a id="r76"></a>R76 | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350` | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:14` |
| <a id="r77"></a>R77 | `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350` | `InsQuoteEngine>>lookupTerritory:into:` (E:90–104) | `tables/territory-factors.dat:15` |
| <a id="r78"></a>R78 | `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L469` | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:3` |
| <a id="r79"></a>R79 | `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L469` | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:4` |
| <a id="r80"></a>R80 | `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L469` | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:5` |
| <a id="r81"></a>R81 | `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L469` | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:6` |
| <a id="r82"></a>R82 | `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L469` | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:7` |
| <a id="r83"></a>R83 | `RATEPREM.cbl:1000-RATE-POLICY L239-L262`; `RATEPREM.cbl:1100-VALIDATE-LINE L276-L281`; `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L464` | `InsQuoteEngine>>quote:` (E:28–39), `InsQuoteEngine>>validateLine:into:` (E:59–61), `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157); `InsQuoteEngine>>validateLine:into:` (E:59–61); `InsQuoteEngine>>quote:` (E:28–39) | `tables/minimum-premium.dat:8` |
| <a id="r84"></a>R84 | `RATEPREM.cbl:2300-LOOKUP-OVERRIDE L368-L382` | `InsQuoteEngine>>lookupOverride:into:` (E:107–117) | `tables/overrides.dat:3` |
| <a id="r85"></a>R85 | `RATEPREM.cbl:2300-LOOKUP-OVERRIDE L368-L382` | `InsQuoteEngine>>lookupOverride:into:` (E:107–117) | `tables/overrides.dat:4` |
| <a id="r86"></a>R86 | `RATEPREM.cbl:2300-LOOKUP-OVERRIDE L368-L382` | `InsQuoteEngine>>lookupOverride:into:` (E:107–117) | `tables/overrides.dat:5`; `tables/line-eligibility.dat:5` |
| <a id="r87"></a>R87 | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY L291-L310` | `InsQuoteEngine>>checkEligibility:into:` (E:69–76) | `tables/line-eligibility.dat:3–6` |
| <a id="r88"></a>R88 | `RATEPREM.cbl:2000-CHECK-ELIGIBILITY L291-L310`; `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335`; `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350`; `RATEPREM.cbl:2300-LOOKUP-OVERRIDE L367-L382`; `RATEPREM.cbl:3500-MINIMUM-PREMIUM L446-L464` | `InsRatingTables>>rowsIn:` (T:39–43); `InsQuoteEngine>>checkEligibility:into:` (E:69–76), `InsQuoteEngine>>lookupClassRate:into:` (E:80–87), `InsQuoteEngine>>lookupTerritory:into:` (E:90–104), `InsQuoteEngine>>lookupOverride:into:` (E:107–117), `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/class-factors.dat:5`; `tables/class-factors.dat:6`; `tables/territory-factors.dat:6`; `tables/territory-factors.dat:7` |
| <a id="r89"></a>R89 | `RATEPREM.cbl:2100-LOOKUP-CLASS L318-L335`; `RATEPREM.cbl:2200-LOOKUP-TERRITORY L338-L350`; `RATEPREM.cbl:2300-LOOKUP-OVERRIDE L367-L382` | `InsRatingTables>>row:from:inForceOn:` (T:46–53); `InsQuoteEngine>>lookupClassRate:into:` (E:80–87), `InsQuoteEngine>>lookupTerritory:into:` (E:90–104), `InsQuoteEngine>>lookupOverride:into:` (E:107–117) | `tables/class-factors.dat:5–6`; `tables/territory-factors.dat:6–7`; `tables/overrides.dat:3–5` |
| <a id="r90"></a>R90 | `RATEPREM.cbl:3000-BASE-PREMIUM L384-L387`; `RATEPREM.cbl:3100-EXPERIENCE-MOD L389-L398` | `InsQuoteEngine>>round:scale:` (E:22–25); `InsQuoteEngine>>basePremium:quote:` (E:120–124) | — |
| <a id="r91"></a>R91 | `RATEPREM.cbl:1000-RATE-POLICY L254-L256`; `RATEPREM.cbl:3100-EXPERIENCE-MOD L389-L398`; `RATEPREM.cbl:3200-DEDUCTIBLE-CREDIT L401-L413` | `InsQuoteEngine>>rate:into:` (E:43–55), `InsQuoteEngine>>experienceMod:premium:` (E:127–133), `InsQuoteEngine>>deductibleCredit:premium:` (E:136–144) | — |
| <a id="r92"></a>R92 | `RATEPREM.cbl:1000-RATE-POLICY L257-L258`; `RATEPREM.cbl:3300-SCHEDULE-MOD L415-L423`; `RATEPREM.cbl:3400-MULTI-POLICY L425-L429` | `InsQuoteEngine>>rate:into:` (E:43–55), `InsQuoteEngine>>scheduleMod:premium:` (E:160–164), `InsQuoteEngine>>multiPolicy:premium:` (E:167–170) | — |
| <a id="r93"></a>R93 | `RATEPREM.cbl:1000-RATE-POLICY L235-L238`; `RATEPREM.cbl:3500-MINIMUM-PREMIUM L465-L469` | `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:3–7` |
| <a id="r94"></a>R94 | `RATEPREM.cbl:1000-RATE-POLICY L254-L261`; `RATEPREM.cbl:3500-MINIMUM-PREMIUM L465-L469` | `InsQuoteEngine>>rate:into:` (E:43–55), `InsQuoteEngine>>applyMinimum:premium:quote:` (E:147–157) | `tables/minimum-premium.dat:3–6` |
| <a id="r95"></a>R95 | `copybooks/POLREC.cpy L17-L17`; `RATEPREM.cbl:1000-RATE-POLICY L231-L262` | `InsQuoteEngine>>endorsements:premium:` (E:180–181) | — |
| <a id="r96"></a>R96 | `copybooks/POLREC.cpy L16-L16`; `RATEPREM.cbl:1000-RATE-POLICY L231-L262` | `InsQuoteEngine>>endorsements:premium:` (E:178–179) | — |
| <a id="r97"></a>R97 | `copybooks/POLREC.cpy L16-L16`; `RATEPREM.cbl:1000-RATE-POLICY L231-L262` (unsigned input; no charge) | `InsQuoteEngine>>endorsements:premium:` (E:178–179) | — |
| <a id="r98"></a>R98 | `RATEPREM.cbl:1000-RATE-POLICY L253-L262` (no endorsements) | `InsQuoteEngine>>endorsements:premium:` (E:180–183), `InsQuoteEngine>>wholeDollars:` (E:190–192), `InsQuoteEngine>>round:scale:` (E:22–25) | — |
| <a id="r99"></a>R99 | `RATEPREM.cbl:1000-RATE-POLICY L253-L262` (no endorsements) | `InsQuoteEngine>>endorsements:premium:` (E:173–187) | — |
| <a id="r100"></a>R100 | `RATEPREM.cbl:3600-POLICY-FEE L471-L473` | `InsQuoteEngine>>rate:into:` (E:43–55) | — |
| <a id="r101"></a>R101 | `copybooks/POLREC.cpy L16-L16`; `RATEPREM.cbl:1000-RATE-POLICY L231-L262` | `InsQuoteEngine>>endorsements:premium:` (E:178–179) | — |
| <a id="r102"></a>R102 | `copybooks/POLREC.cpy L17-L17`; `RATEPREM.cbl:1000-RATE-POLICY L231-L262` | `InsQuoteEngine>>endorsements:premium:` (E:180–181) | — |
| <a id="r103"></a>R103 | `copybooks/POLREC.cpy L18-L18`; `RATEPREM.cbl:1000-RATE-POLICY L231-L262` | `InsQuoteEngine>>endorsements:premium:` (E:182–183) | — |
| <a id="r104"></a>R104 | `copybooks/POLREC.cpy L19-L19`; `RATEPREM.cbl:1000-RATE-POLICY L231-L262` | `InsQuoteEngine>>endorsements:premium:` (E:184–185) | — |

## Quote-screen input contract

- `InsQuoteScreen>>handle:` and `InsQuoteScreen>>policyFrom:`: `smalltalk/src/InsRating/InsQuoteScreen.class.st:28–58`.
- `InsQuoteScreen>>pageFor:quote:` and `InsQuoteScreen>>money:`: `smalltalk/src/InsRating/InsQuoteScreen.class.st:61–104`.
