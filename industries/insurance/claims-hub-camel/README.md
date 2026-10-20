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

## Container and chart

`Dockerfile` is a multi-stage build (Temurin 21 JDK builder, Temurin 21 JRE runtime) running as uid 1001, with a `HEALTHCHECK` on `GET /health` (port 8092, Spring Boot actuator). The image build skips tests because the corpus lives outside the build context; CI runs them in the `golden` job. Pass `--build-arg MVNW_REPOURL=<mirror>` and `--secret id=m2settings,src=<settings.xml>` to build behind a Maven mirror; neither is baked into the image.

The Helm chart is `infrastructure/helm/claims-hub-camel/` (ClusterIP service only, resources set, liveness and readiness probes on `/health`):

```bash
helm template claims-hub-camel infrastructure/helm/claims-hub-camel --set image.tag=dev | kubeconform -strict -summary
```

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

## ClaimTriage rules

The BRE policy `ClaimTriage` 1.2 (`Rules/ClaimTriagePolicy.xml`) is kept as data in
[`src/main/resources/rules/claim-triage.csv`](src/main/resources/rules/claim-triage.csv): one row per
rule with `name`, `priority`, `condition`, `outcome` and `reason`. Thresholds and the fast-track cause
list are literals in the `condition` column and are read when the table loads; the Java code holds none
of them. The table to load is `claimshub.triage.rules-table` in `application.yaml`.

Condition syntax: clauses joined by `and`, each `Fact op literal` (`==`, `!=`, `>`, `>=`, `<`, `<=`) or
`Fact in (A,B,C)`. Literals are `true`/`false`, a decimal (compared by value with `BigDecimal`), or a
single-quoted string. `Outcome` is the outcome set so far, empty before any rule sets one.

`TriageEvaluator` applies the agenda of `tools/triage_reference.py`: descending priority (file order within
a priority), each condition sees the outcome set so far, the first outcome set wins, every fired rule
appends its reason. `direct:claimTriage` takes a `TriageFacts` document and returns the `TriageResult`
with the outcome on the `TriageOutcome` header.

### Triage checks

```bash
(cd ../biztalk-claims-intake && python3 tools/triage_reference.py check)   # reference re-run, goldens current
./mvnw verify                                                               # parity, BRE name guard, unit tests
cat target/parity/triage-parity.md                                          # side-by-side report
```

- `TriageParityTest` runs the table over the 16 `corpus/golden/triage-facts` documents and compares rules
  fired, outcome and reasons with `corpus/golden/triage/*.json`; any difference fails the build.
- `RulesTableMatchesBreExportTest` fails when the table and the BRE export name different rules, or when a
  rule's priority, outcome or reason differs from the export.
