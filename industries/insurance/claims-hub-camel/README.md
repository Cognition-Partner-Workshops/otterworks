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

## Container and chart

`Dockerfile` is a multi-stage build (Temurin 21 JDK builder, Temurin 21 JRE runtime) running as uid 1001, with a `HEALTHCHECK` on `GET /health` (port 8092, Spring Boot actuator). The image build skips tests because the corpus lives outside the build context; CI runs them in the `golden` job. Pass `--build-arg MVNW_REPOURL=<mirror>` and `--secret id=m2settings,src=<settings.xml>` to build behind a Maven mirror; neither is baked into the image.

The Helm chart is `infrastructure/helm/claims-hub-camel/` (ClusterIP service only, resources set, liveness and readiness probes on `/health`):

```bash
helm template claims-hub-camel infrastructure/helm/claims-hub-camel --set image.tag=dev | kubeconform -strict -summary
```
