# claims-hub-camel

The BizTalk claims hub (`../biztalk-claims-intake/`) re-hosted on Java 21, Spring Boot 3.3 and Apache Camel 4.8. The Saxon behaviour corpus of the fixture is the contract: a map is converted when its golden test passes byte for byte over every corpus message listed for it in `corpus/manifest.yaml`.

```bash
./mvnw verify                         # all golden tests; per-map tables land in target/golden-report/<MapName>.md
./mvnw test -Dtest=<MapName>GoldenTest
```

Tests read the fixture from `-Dclaims.fixture.dir` (default `../biztalk-claims-intake`).

## Conventions for a converted map

| Piece | Where | Rule |
| --- | --- | --- |
| Route | `src/main/java/example/claimshub/maps/<MapName>Route.java` | A `RouteBuilder` `@Component` consuming `MapEndpoints.of("<MapName>")` (`direct:map.<MapName>`), route id `MapEndpoints.routeId("<MapName>")` (`map.<MapName>`); the golden test fails fast if the route is missing. Body in is the source message, body out the target message. |
| Pure map | `src/main/resources/maps/<MapName>.xslt` | The compiled XSLT, run with `xslt-saxon:maps/<MapName>.xslt`. Saxon is pinned to 12.5, the line that wrote the goldens. |
| Map with logic | `src/main/java/example/claimshub/maps/<MapName>Transformer.java` | A Java transformer called from the route. Money is `BigDecimal`; every rounding call names its mode and matches the source (`RoundingMode.HALF_EVEN` where .NET `Math.Round` ran). |
| Golden test | `src/test/java/example/claimshub/maps/<MapName>GoldenTest.java` | `extends GoldenMapTest`, returns the manifest name from `mapName()`. One dynamic test per corpus message. |

A message that cannot be made byte-identical stays red: its dynamic test fails, and `knownCauses()` names the cause in the failure and in the report row. It is never skipped or relaxed.

`GoldenMapTestSelfTest` proves the harness through Camel with an identity route over the `CanonicalClaim_to_PolicyInqRq` goldens; `CorpusManifestTest` checks the manifest still lists the eight maps and 112 goldens.

## FnolIntake route (`src/main/java/example/claimshub/fnol/`)

`FnolIntakeRoute` is the `FnolIntake` orchestration. FNOLs come in on `direct:fnol.in` (what the receive pipeline hands the MessageBox).

| XLANG/s | Camel |
| --- | --- |
| `ClaimNumberCorrelation`, Listen with `Receive_Correction` and the 15 minute `Delay_CorrectionWindow` | `fnol.receive`: aggregator on the promoted `ClaimNumber`, the latest FNOL wins, complete on the second message or after `claimshub.fnol.correction-window` (15m) |
| The four maps | `xslt-saxon` over the fixture's `Maps/` (the `.golden.xslt` twin for `InsertClaim_to_TriageFacts`); the two-source map reads the `aggschema` `Root` |
| `PolicyLookup` / `ClaimsDb` WCF-SQL ports | `port.policy-lookup`, `port.insert-claim`: PostgreSQL 16 functions `usp_get_policy_as_of`, `usp_insert_claim` (`src/test/resources/db/wcf-sql-stand-in.sql`) |
| `Call_Rules ClaimTriage` | `ClaimTriage`; `GoldenTriageStub` answers from `corpus/golden/triage/` until the rules-table conversion is merged |
| `Decide_Outcome`, `Decide_Assignment` | declines end `TERMINATED` with no insert; fast tracks are inserted and get no assignment request |
| `sp_Fraud_Referral_FILE`, `sp_Declines_FILE`, `sp_GlassVendor_FastTrack_SFTP` | `messagebox.triage-facts`, `messagebox.insert-claim`: content-based routes on the promoted `TriageOutcome` (and `LossCauseCd`) |

`FnolIntakeCorrelationTest` and `FnolIntakeCorpusTest` start a PostgreSQL 16 container through Testcontainers (Docker required) and write `target/fnol-parity/REPORT.md`, one row per corpus FNOL.
