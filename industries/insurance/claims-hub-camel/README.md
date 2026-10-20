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

## Conventions for a converted orchestration

| Piece | Where | Rule |
| --- | --- | --- |
| Route | `src/main/java/example/claimshub/orchestrations/<Name>Route.java` | Consumes `OrchestrationEndpoints.of("<Name>")` (`direct:orchestration.<Name>`), route id `orchestration.<Name>`. Body in is the message the activating receive took. A parallel shape is a `multicast` with an aggregation strategy; maps it calls go through their `direct:map.*` routes. |
| Characterization test | `src/test/java/example/claimshub/orchestrations/<Name>OrchestrationTest.java` | Written from the XLANG/s before the route; runs against real ports in Testcontainers and checks every corpus output byte for byte. |

`AdjusterAssignment` ports: the WCF-SQL roster port is `jdbc:dataSource` calling `usp_get_adjuster_roster(region, skill, as_of)` (the test schema in `src/test/resources/roster/schema.sql`, seeded from `corpus/stubs/roster`), the FILE archive port is `file:{{claimshub.archive.dir}}`, and the SMTP port is `smtp://{{claimshub.smtp.host}}:{{claimshub.smtp.port}}` with the notice text as the body and the notice attached. The test needs Docker (PostgreSQL 16 and MailHog).

`GoldenMapTestSelfTest` proves the harness through Camel with an identity route over the `CanonicalClaim_to_PolicyInqRq` goldens; `CorpusManifestTest` checks the manifest still lists the eight maps and 112 goldens.
